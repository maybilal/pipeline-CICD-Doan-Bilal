"""
Tests du NIVEAU 3, option 3 : extraction de transactions depuis du texte (SLM).

- Les tests "sans SLM" vérifient notre code Python (construction de la date,
  validation) avec des réponses de SLM préparées à l'avance : ils tournent partout.
- Les tests "avec SLM" interrogent le vrai modèle : ils sont "sautés" si le
  service n'est pas démarré (docker compose up -d slm && python preparer_slm.py).
"""
import urllib.request
from decimal import Decimal

import pytest

import src.pipeline.slm as slm
from generate_textes import ATTENDU, MESSAGES
from src.pipeline.pipeline import executer_pipeline
from src.pipeline.validation import DonneeInvalide, valider_transaction, valider_transactions
from tests.outils import base_vide, lire

TEXTE = "\n".join(MESSAGES["messages_001.txt"]).encode("utf-8")


def slm_disponible() -> bool:
    try:
        with urllib.request.urlopen(slm.SLM_URL + "/api/tags", timeout=2) as r:
            return slm.MODELE in r.read().decode()
    except Exception:
        return False


besoin_slm = pytest.mark.skipif(not slm_disponible(), reason="SLM (Ollama + modèle) non disponible")

PHRASE_SUJET = MESSAGES["messages_001.txt"][0]     # "Le 12 septembre à 14h30..." (sans année)
REPONSE_SUJET = {   # ce que le SLM devrait répondre pour cette phrase
    "jour": 12, "mois": 9, "heure": 14, "minute": 30,
    "iban_emetteur": "FR76 3000 1007 9412 3456 7890 185", "banque_emettrice": "BNP Paribas",
    "iban_destinataire": "DE89 3704 0044 0532 0130 00", "montant": 6200,
}


# --- Sans SLM : notre code Python ---------------------------------------------

def test_reponse_du_slm_vers_transaction_valide():
    transaction = valider_transaction(slm.vers_transaction(REPONSE_SUJET, PHRASE_SUJET))
    assert transaction["datetime_transaction"] == "2026-09-12 14:30:00"   # année par défaut
    assert transaction["iban_origine"] == "FR7630001007941234567890185"
    assert transaction["pays_destinataire"] == "DE"
    assert transaction["montant"] == Decimal("6200.00")


def test_une_erreur_du_slm_est_rattrapee_par_la_validation():
    """Si le SLM se trompe (ici : un chiffre de l'IBAN oublié), le fichier est rejeté."""
    mauvaise = {**REPONSE_SUJET, "iban_emetteur": "FR76 3000 1007 9412 3456 7890 18"}
    with pytest.raises(DonneeInvalide):
        valider_transaction(slm.vers_transaction(mauvaise, PHRASE_SUJET))


def test_mois_impossible_rejete():
    with pytest.raises(DonneeInvalide):
        valider_transaction(slm.vers_transaction({**REPONSE_SUJET, "mois": 13}, PHRASE_SUJET))


@pytest.mark.parametrize("phrase, annee", [
    ("Le 12 septembre à 14h30, le compte FR76 3000 2011 ...", 2026),   # absente -> par défaut
    ("Virement effectué le 3 octobre 2025 à 9h05", 2025),
    ("Le 1er mars 2024, ...", 2024),
    ("Le 20/10/2027 à 18h00, ...", 2027),
])
def test_l_annee_est_trouvee_par_python_et_pas_par_le_slm(phrase, annee):
    """Les chiffres d'un IBAN (ex. 2011) ne doivent pas être pris pour une année."""
    assert slm.trouver_annee(phrase) == annee


def test_lignes_vides_et_commentaires_ignores():
    assert slm.phrases("# commentaire\n\nLigne 1\n  \nLigne 2\n") == ["Ligne 1", "Ligne 2"]


def test_texte_dans_la_pipeline_avec_un_slm_simule(monkeypatch):
    """Le texte rejoint le même flux que les CSV (SLM remplacé par des réponses fixes)."""
    monkeypatch.setattr(slm, "_pret", True)
    monkeypatch.setattr(slm, "interroger_slm", lambda phrase: REPONSE_SUJET)
    conn = base_vide()
    try:
        bilan = executer_pipeline([("message.txt", lambda: b"Une phrase\n")], attente=0)
        assert bilan["traites"] == ["message.txt"]
        assert lire(conn, "SELECT montant, flag FROM transactions") == [(Decimal("6200.00"), True)]
    finally:
        conn.close()


# --- Avec le vrai SLM -----------------------------------------------------------

@besoin_slm
def test_le_slm_extrait_correctement_les_trois_phrases():
    obtenues = valider_transactions(slm.transactions_depuis_texte(TEXTE), "messages_001.txt")
    assert [
        (t["datetime_transaction"], t["iban_origine"], t["banque_source"],
         t["iban_destinataire"], str(t["montant"]))
        for t in obtenues
    ] == ATTENDU


@besoin_slm
def test_texte_vers_base_avec_le_vrai_slm():
    conn = base_vide()
    try:
        bilan = executer_pipeline([("messages_001.txt", lambda: TEXTE)], attente=0)
        assert bilan["traites"] == ["messages_001.txt"]
        assert lire(conn, "SELECT montant, flag FROM transactions ORDER BY datetime_transaction") == [
            (Decimal("6200.00"), True), (Decimal("1480.75"), False), (Decimal("320.00"), False),
        ]
    finally:
        conn.close()