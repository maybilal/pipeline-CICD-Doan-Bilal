"""
OCR (Niveau 3, option 2) : lire une transaction dans une IMAGE.

    Image -> OCR -> Extraction des informations -> (Validation -> Traitement -> Base)

- L'OCR (Tesseract) transforme les pixels de l'image en TEXTE.
- L'extraction repère, dans ce texte, les informations utiles
  ("Montant : 6 200,00 EUR" -> montant = "6 200,00 EUR").
- La validation (validation.py) vérifie et nettoie ensuite les valeurs.
"""
import io
import os
import re
import shutil
from pathlib import Path

import pytesseract
from PIL import Image

# Sous Windows, Tesseract n'est souvent pas dans le PATH : on le cherche à son
# emplacement d'installation par défaut. TESSERACT_CMD permet d'en donner un autre.
_WINDOWS = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")
elif not shutil.which("tesseract") and _WINDOWS.exists():
    pytesseract.pytesseract.tesseract_cmd = str(_WINDOWS)


def tesseract_disponible() -> bool:
    try:
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def texte_depuis_image(contenu: bytes) -> str:
    """OCR : renvoie le texte lu dans l'image."""
    image = Image.open(io.BytesIO(contenu)).convert("L")       # en niveaux de gris
    langues = "fra" if "fra" in pytesseract.get_languages() else "eng"
    # --psm 6 : "l'image est un bloc de texte uniforme" (idéal pour un reçu)
    return pytesseract.image_to_string(image, lang=langues, config="--psm 6")


# Pour chaque information : un "motif" qui repère la ligne correspondante.
# Les motifs tolèrent une première lettre mal lue ("émetteur" lu "Xmetteur")
# et les espaces en trop.
MOTIFS = {
    "datetime_transaction": r"date\s*:?\s*(.+)",
    "iban_origine":         r"iban\s+\S?metteur\s*:?\s*(.+)",
    "banque_source":        r"banque\s+\S?mettrice\s*:?\s*(.+)",
    "iban_destinataire":    r"iban\s+destinataire\s*:?\s*(.+)",
    "montant":              r"montant\s*:?\s*(.+)",
}


def extraire_transaction(texte: str) -> dict:
    """Repère les informations dans le texte lu par l'OCR (une transaction par image)."""
    transaction = {}
    for ligne in texte.splitlines():
        for champ, motif in MOTIFS.items():
            trouve = re.match(motif, ligne.strip(), flags=re.IGNORECASE)
            if trouve and champ not in transaction:
                transaction[champ] = trouve.group(1).strip()
    return transaction


def transactions_depuis_image(contenu: bytes) -> list[dict]:
    """Image -> OCR -> extraction. La validation est faite ensuite par la pipeline."""
    return [extraire_transaction(texte_depuis_image(contenu))]
