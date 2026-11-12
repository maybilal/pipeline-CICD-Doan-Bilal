"""
Niveau 3 (option 3) — Génère des fichiers de TEXTE BRUT décrivant des
transactions, comme des messages ou des notes écrits par des humains.

Chaque ligne décrit une transaction, avec des formulations variées.
Les valeurs sont connues d'avance (elles servent aux tests).

Usage :
    python generate_textes.py                  # dans data_textes/
    python generate_textes.py --dossier autre_dossier
"""
import argparse
from pathlib import Path

MESSAGES = {
    "messages_001.txt": [
        # Même phrase que l'exemple du sujet, mais avec des IBAN valides
        # (ceux du sujet sont fictifs : leur clé de contrôle est fausse).
        "Le 12 septembre à 14h30, le compte FR76 3000 1007 9412 3456 7890 185 ouvert chez "
        "BNP Paribas a envoyé 6200 € vers le compte DE89 3704 0044 0532 0130 00 appartenant "
        "à une banque allemande.",
        "Virement de 1 480,75 euros effectué le 3 octobre 2026 à 9h05 par CaixaBank depuis le "
        "compte ES91 2100 0418 4502 0005 1332 au profit du compte IT60 X054 2811 1010 0000 0123 456.",
        "Le 20/10/2026 à 18h00, Commerzbank a transféré 320 € du compte "
        "DE89 3704 0044 0532 0130 00 vers le compte FR76 3000 4000 0312 3456 7890 143.",
    ],
}

# Ce que la pipeline doit obtenir après SLM + validation (utilisé par les tests)
ATTENDU = [
    ("2026-09-12 14:30:00", "FR7630001007941234567890185", "BNP Paribas",
     "DE89370400440532013000", "6200.00"),
    ("2026-10-03 09:05:00", "ES9121000418450200051332", "CaixaBank",
     "IT60X0542811101000000123456", "1480.75"),
    ("2026-10-20 18:00:00", "DE89370400440532013000", "Commerzbank",
     "FR7630004000031234567890143", "320.00"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des fichiers texte de transactions.")
    parser.add_argument("--dossier", default="data_textes")
    args = parser.parse_args()

    dossier = Path(args.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    for nom, lignes in MESSAGES.items():
        (dossier / nom).write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"{len(MESSAGES)} fichier(s) texte généré(s) dans '{dossier}/'")


if __name__ == "__main__":
    main()
