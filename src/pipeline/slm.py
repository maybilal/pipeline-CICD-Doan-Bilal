"""
SLM (Niveau 3, option 3) : extraire une transaction d'un TEXTE BRUT avec un
petit modèle de langage (Small Language Model), qui tourne en local avec Ollama.

    Texte -> SLM -> (Validation -> Traitement -> Base)

Répartition des rôles :
  - le SLM COMPREND la phrase et en ressort les informations, dans un format
    imposé (un "schéma JSON") : jour, mois, montant, IBAN...
  - Python fait tout ce qui doit être EXACT : trouver l'année, construire la
    date, nettoyer et vérifier les IBAN (validation.py).
    On ne fait pas confiance aveuglément au SLM.
"""
import json
import os
import re
import urllib.error
import urllib.request

from src.pipeline.retry import avec_retry

SLM_URL = os.getenv("SLM_URL", "http://localhost:11434")
MODELE = os.getenv("SLM_MODELE", "qwen2.5:1.5b")
# Année utilisée quand la phrase n'en donne pas ("le 12 septembre").
# Fixée (et non "l'année en cours") pour que le résultat soit reproductible.
ANNEE_PAR_DEFAUT = int(os.getenv("SLM_ANNEE_PAR_DEFAUT", "2026"))

ERREURS_TEMPORAIRES_SLM = (urllib.error.URLError, ConnectionError, TimeoutError)

# Le format de réponse IMPOSÉ au SLM : il ne peut pas répondre autre chose.
SCHEMA = {
    "type": "object",
    "properties": {
        "jour": {"type": "integer"},
        "mois": {"type": "integer"},
        "heure": {"type": "integer"},
        "minute": {"type": "integer"},
        "iban_emetteur": {"type": "string"},
        "banque_emettrice": {"type": "string"},
        "iban_destinataire": {"type": "string"},
        "montant": {"type": "number"},
    },
    "required": ["jour", "mois", "heure", "minute", "iban_emetteur",
                 "banque_emettrice", "iban_destinataire", "montant"],
}

CONSIGNES = """Tu extrais UNE transaction bancaire d'une phrase en français.
Règles :
- mois en chiffre : janvier=1, février=2, ..., décembre=12 ;
- si l'heure n'est pas écrite, heure=0 et minute=0 ;
- recopie chaque IBAN EXACTEMENT comme il est écrit, caractère par caractère ;
- l'émetteur est le compte qui ENVOIE l'argent, le destinataire celui qui le REÇOIT ;
- banque_emettrice = nom de la banque de l'émetteur, ou "" si elle n'est pas nommée ;
- montant = nombre, sans symbole (1 480,75 € -> 1480.75)."""

# Un exemple résolu : les petits modèles suivent beaucoup mieux un exemple.
EXEMPLE_QUESTION = ("Le 5 mars 2025 à 8h15, Banque Exemple a versé 2 300,50 € depuis le compte "
                    "AB12 3456 7890 vers le compte CD98 7654 3210.")
EXEMPLE_REPONSE = json.dumps({
    "jour": 5, "mois": 3, "heure": 8, "minute": 15,
    "iban_emetteur": "AB12 3456 7890", "banque_emettrice": "Banque Exemple",
    "iban_destinataire": "CD98 7654 3210", "montant": 2300.50,
}, ensure_ascii=False)


# --- Communication avec Ollama -------------------------------------------------

def _requete(chemin: str, donnees: dict | None = None, delai: int = 120) -> dict:
    """Envoie une requête HTTP à Ollama et renvoie sa réponse JSON."""
    corps = json.dumps(donnees).encode() if donnees is not None else None
    requete = urllib.request.Request(
        SLM_URL + chemin, data=corps, headers={"Content-Type": "application/json"},
        method="POST" if corps else "GET",
    )
    with urllib.request.urlopen(requete, timeout=delai) as reponse:
        return json.loads(reponse.read())


def preparer_slm(max_tentatives: int = 6) -> None:
    """
    Attend que le service Ollama réponde, puis télécharge le modèle s'il n'est
    pas encore présent (une seule fois : il est ensuite gardé dans un volume Docker).
    """
    modeles = avec_retry(
        lambda: _requete("/api/tags", delai=5),
        description="la connexion au service SLM (Ollama)",
        erreurs_temporaires=ERREURS_TEMPORAIRES_SLM,
        max_tentatives=max_tentatives,
        attente_initiale=1,
    )
    presents = [m["name"] for m in modeles.get("models", [])]
    if MODELE in presents:
        print(f"✅ Modèle {MODELE} déjà disponible")
        return
    print(f"⬇️  Téléchargement du modèle {MODELE} (une seule fois, environ 1 Go)...")
    _requete("/api/pull", {"model": MODELE, "stream": False}, delai=1800)
    print(f"✅ Modèle {MODELE} téléchargé")


def interroger_slm(phrase: str) -> dict:
    """Pose la question au SLM et renvoie sa réponse (un dictionnaire)."""
    reponse = avec_retry(
        lambda: _requete("/api/chat", {
            "model": MODELE,
            "stream": False,
            "format": SCHEMA,                              # réponse forcée au bon format
            "options": {"temperature": 0, "seed": 42},     # pas de hasard : reproductible
            "messages": [
                {"role": "system", "content": CONSIGNES},
                {"role": "user", "content": EXEMPLE_QUESTION},
                {"role": "assistant", "content": EXEMPLE_REPONSE},
                {"role": "user", "content": phrase},
            ],
        }),
        description="l'appel au SLM",
        erreurs_temporaires=ERREURS_TEMPORAIRES_SLM,
        max_tentatives=3,
        attente_initiale=1,
    )
    return json.loads(reponse["message"]["content"])


# --- De la réponse du SLM à une transaction -----------------------------------

MOIS = r"(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)"


def trouver_annee(phrase: str) -> int:
    """
    Cherche l'année DANS LA PHRASE, uniquement à côté d'une date
    ("3 octobre 2026", "20/10/2026"), pour ne pas confondre avec les chiffres
    d'un IBAN. On ne la demande PAS au SLM : quand elle est absente, il avait
    tendance à en inventer une (une "hallucination").
    """
    trouve = (re.search(rf"\b\d{{1,2}}(?:er)?\s+{MOIS}\s+(\d{{4}})\b", phrase, re.IGNORECASE)
              or re.search(r"\b\d{1,2}/\d{1,2}/(\d{4})\b", phrase))
    return int(trouve.group(1)) if trouve else ANNEE_PAR_DEFAUT


def vers_transaction(extrait: dict, phrase: str) -> dict:
    """
    Transforme la réponse du SLM en transaction au format de la pipeline.
    Fonction pure. Les valeurs sont vérifiées ensuite par validation.py
    (par exemple, un mois=13 donnera une date invalide => fichier rejeté).
    """
    annee = trouver_annee(phrase)
    date = (f"{annee:04d}-{extrait.get('mois', 0):02d}-{extrait.get('jour', 0):02d} "
            f"{extrait.get('heure', 0):02d}:{extrait.get('minute', 0):02d}:00")
    return {
        "datetime_transaction": date,
        "iban_origine": extrait.get("iban_emetteur", ""),
        "banque_source": extrait.get("banque_emettrice", ""),
        "iban_destinataire": extrait.get("iban_destinataire", ""),
        "montant": str(extrait.get("montant", "")),
    }


def phrases(texte: str) -> list[str]:
    """Une transaction par ligne ; les lignes vides et les commentaires (#) sont ignorés."""
    return [l.strip() for l in texte.splitlines() if l.strip() and not l.strip().startswith("#")]


_pret = False


def transactions_depuis_texte(contenu: bytes) -> list[dict]:
    """Texte -> SLM (une phrase à la fois) -> transactions. Validation faite ensuite."""
    global _pret
    if not _pret:               # le SLM n'est préparé que si on a vraiment du texte à lire
        preparer_slm()
        _pret = True
    resultat = []
    for phrase in phrases(contenu.decode("utf-8")):
        extrait = interroger_slm(phrase)
        print(f"   🤖 SLM : « {phrase[:60]}... » -> {extrait}")
        resultat.append(vers_transaction(extrait, phrase))
    return resultat