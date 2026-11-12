"""
VALIDATION / TRANSFORMATION : vérifier qu'une transaction est correcte et la
mettre au format attendu par le traitement, QUELLE QUE SOIT sa source
(CSV, image lue par OCR, texte lu par un SLM).

    Chargement -> VALIDATION -> Traitement

Une transaction invalide fait rejeter tout le fichier (DonneeInvalide) :
rien n'est inséré, et l'erreur est affichée clairement.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re

COLONNES = [
    "datetime_transaction", "iban_origine", "pays_source", "banque_source",
    "iban_destinataire", "pays_destinataire", "montant",
]

FORMATS_DATE = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")


class DonneeInvalide(Exception):
    """Une donnée ne respecte pas le format attendu."""


def iban_valide(iban: str) -> bool:
    """
    Vérifie la clé de contrôle d'un IBAN (norme ISO 13616, "modulo 97").
    Comme le dernier chiffre d'un numéro de sécurité sociale, elle permet de
    détecter une faute de frappe... ou une erreur de lecture de l'OCR.
    """
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", iban):
        return False
    reorganise = iban[4:] + iban[:4]
    nombre = "".join(str(int(c, 36)) for c in reorganise)   # A=10, B=11, ... Z=35
    return int(nombre) % 97 == 1


def normaliser_iban(valeur) -> str:
    """'fr76 3000 1007...' -> 'FR7630001007...' (majuscules, sans espaces)."""
    return re.sub(r"\s+", "", str(valeur or "")).upper()


def normaliser_montant(valeur) -> Decimal:
    """
    Accepte 6200, '6200.00', '6 200,00 €', '6,200.50 EUR'...
    Le dernier séparateur ("," ou ".") est considéré comme la virgule décimale.
    """
    if isinstance(valeur, Decimal):
        return valeur
    texte = re.sub(r"[^\d,.\-]", "", str(valeur))       # garde chiffres, signes et séparateurs
    if "," in texte and "." in texte:
        decimal = "," if texte.rfind(",") > texte.rfind(".") else "."
        millier = "." if decimal == "," else ","
        texte = texte.replace(millier, "").replace(decimal, ".")
    else:
        texte = texte.replace(",", ".")
    try:
        return Decimal(texte).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise DonneeInvalide(f"montant illisible : {valeur!r}")


def normaliser_date(valeur) -> str:
    texte = str(valeur or "").strip()
    for fmt in FORMATS_DATE:
        try:
            return datetime.strptime(texte, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    raise DonneeInvalide(f"date illisible : {valeur!r}")


def valider_transaction(brute: dict) -> dict:
    """
    Renvoie une NOUVELLE transaction propre, ou lève DonneeInvalide.
    Fonction pure : la transaction reçue n'est pas modifiée.
    """
    iban_o = normaliser_iban(brute.get("iban_origine"))
    iban_d = normaliser_iban(brute.get("iban_destinataire"))
    for nom, iban in (("iban_origine", iban_o), ("iban_destinataire", iban_d)):
        if not iban_valide(iban):
            raise DonneeInvalide(f"{nom} invalide : {iban!r} (format ou clé de contrôle incorrects)")
    if iban_o == iban_d:
        raise DonneeInvalide("l'émetteur et le destinataire sont le même compte")

    montant = normaliser_montant(brute.get("montant"))
    if montant <= 0:
        raise DonneeInvalide(f"montant négatif ou nul : {montant}")

    return {
        "datetime_transaction": normaliser_date(brute.get("datetime_transaction")),
        "iban_origine": iban_o,
        # Le pays se déduit des 2 premières lettres de l'IBAN s'il n'est pas fourni
        "pays_source": (brute.get("pays_source") or iban_o[:2]).upper(),
        "banque_source": (brute.get("banque_source") or "").strip() or "Inconnue",
        "iban_destinataire": iban_d,
        "pays_destinataire": (brute.get("pays_destinataire") or iban_d[:2]).upper(),
        "montant": montant,
    }


def valider_transactions(brutes: list[dict], source: str) -> list[dict]:
    """Valide toutes les transactions d'un fichier, en indiquant la ligne fautive."""
    if not brutes:
        raise DonneeInvalide(f"{source} : aucune transaction trouvée")
    valides = []
    for numero, brute in enumerate(brutes, start=1):
        try:
            valides.append(valider_transaction(brute))
        except DonneeInvalide as erreur:
            raise DonneeInvalide(f"{source}, transaction n°{numero} : {erreur}") from None
    return valides
