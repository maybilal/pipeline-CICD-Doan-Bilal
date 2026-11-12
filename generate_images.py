"""
Niveau 3 (option 2) — Génère des images d'avis de virement, comme une banque
pourrait en scanner.

Comme pour les CSV, les données ne sont PAS aléatoires : on connaît d'avance
ce que l'OCR doit lire, ce qui permet de le tester.

Usage :
    python generate_images.py                      # 2 images dans data_images/
    python generate_images.py --dossier autre_dossier
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Les avis de virement à générer. On écrit les IBAN par groupes de 4 et les
# montants "à la française", comme sur un vrai document : la validation devra
# les remettre au bon format.
AVIS = {
    "recu_001.png": [
        "AVIS DE VIREMENT",
        "",
        "Date : 2026-02-03 10:15:00",
        "IBAN emetteur : FR76 3000 1007 9412 3456 7890 185",
        "Banque emettrice : BNP Paribas",
        "IBAN destinataire : DE89 3704 0044 0532 0130 00",
        "Montant : 6 200,00 EUR",
    ],
    "recu_002.png": [
        "AVIS DE VIREMENT",
        "",
        "Date : 2026-02-04 16:40:00",
        "IBAN emetteur : ES91 2100 0418 4502 0005 1332",
        "Banque emettrice : CaixaBank",
        "IBAN destinataire : IT60 X054 2811 1010 0000 0123 456",
        "Montant : 1 250,50 EUR",
    ],
}


def dessiner_avis(lignes: list[str]) -> Image.Image:
    """Dessine le texte en noir sur fond blanc."""
    police = ImageFont.load_default(size=30)
    image = Image.new("RGB", (1100, 60 + 50 * len(lignes)), "white")
    dessin = ImageDraw.Draw(image)
    for i, ligne in enumerate(lignes):
        dessin.text((40, 30 + 50 * i), ligne, fill="black", font=police)
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des images d'avis de virement.")
    parser.add_argument("--dossier", default="data_images")
    args = parser.parse_args()

    dossier = Path(args.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, lignes in AVIS.items():
        dessiner_avis(lignes).save(dossier / nom)
    print(f"{len(AVIS)} image(s) générée(s) dans '{dossier}/'")


if __name__ == "__main__":
    main()
