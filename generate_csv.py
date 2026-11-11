"""
Étape 1 — Génération de fichiers CSV de transactions financières.

Deux types de fichiers sont produits :
  1. Un fichier de RÉFÉRENCE écrit à la main : on connaît d'avance les
     résultats attendus (sommes, flags). Il servira aux tests d'intégration.
  2. Des fichiers "aléatoires contrôlés" : on utilise une graine (seed) fixe,
     donc les mêmes données sont générées à chaque exécution.

Usage :
    python generate_csv.py                 # 3 fichiers aléatoires + 1 de référence dans ./data
    python generate_csv.py --nb-fichiers 5 --seed 123 --dossier sortie
"""
import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

COLONNES = [
    "datetime_transaction",
    "iban_origine",
    "pays_source",
    "banque_source",
    "iban_destinataire",
    "pays_destinataire",
    "montant",
]

SEUIL_FLAG = 5000  # rappel : une transaction > 5000 sera flaguée à l'étape 2

# Pool FIXE de comptes : un IBAN est toujours associé au même pays et à la même
# banque. Les deux premiers comptes sont dans la même banque, pour que la somme
# "par banque" soit différente de la somme "par IBAN".
COMPTES = {
    "A": {"iban": "FR7630001007941234567890185", "pays": "FR", "banque": "BNP Paribas"},
    "B": {"iban": "FR7630004000031234567890143", "pays": "FR", "banque": "BNP Paribas"},
    "C": {"iban": "DE89370400440532013000", "pays": "DE", "banque": "Commerzbank"},
    "D": {"iban": "DE44500105175407324931", "pays": "DE", "banque": "Deutsche Bank"},
    "E": {"iban": "ES9121000418450200051332", "pays": "ES", "banque": "CaixaBank"},
    "F": {"iban": "IT60X0542811101000000123456", "pays": "IT", "banque": "UniCredit"},
}


def creer_transaction(date: datetime, origine: str, destinataire: str, montant: float) -> dict:
    """Construit une ligne CSV à partir de deux clés de compte et d'un montant."""
    src, dst = COMPTES[origine], COMPTES[destinataire]
    return {
        "datetime_transaction": date.strftime("%Y-%m-%d %H:%M:%S"),
        "iban_origine": src["iban"],
        "pays_source": src["pays"],
        "banque_source": src["banque"],
        "iban_destinataire": dst["iban"],
        "pays_destinataire": dst["pays"],
        "montant": f"{montant:.2f}",
    }


def transactions_reference() -> list[dict]:
    """
    Jeu de données écrit à la main, avec résultats attendus connus :

    Somme envoyée par iban_origine :  A = 12300.00 | B = 5000.01 | C = 250.50 | D = 49.50
    Somme envoyée par banque_source : BNP Paribas = 17300.01 | Commerzbank = 250.50 | Deutsche Bank = 49.50
    Somme reçue par iban_destinataire : C = 12300.01 | D = 5000.00 | A = 250.50 | B = 49.50
    Flags (> 5000) : lignes 3 (5000.01) et 5 (7200.00) uniquement.
    La ligne 2 (5000.00 pile) NE doit PAS être flaguée : on teste la frontière.
    """
    d = datetime(2026, 1, 15, 9, 0, 0)
    return [
        creer_transaction(d,                          "A", "C", 100.00),
        creer_transaction(d + timedelta(minutes=10),  "A", "D", 5000.00),
        creer_transaction(d + timedelta(minutes=20),  "B", "C", 5000.01),
        creer_transaction(d + timedelta(minutes=30),  "C", "A", 250.50),
        creer_transaction(d + timedelta(minutes=40),  "A", "C", 7200.00),
        creer_transaction(d + timedelta(minutes=50),  "D", "B", 49.50),
    ]


def transactions_aleatoires(rng: random.Random) -> list[dict]:
    """Génère entre 5 et 10 transactions pseudo-aléatoires (reproductibles grâce à rng)."""
    cles = list(COMPTES)
    debut = datetime(2026, 1, 1)
    transactions = []
    for _ in range(rng.randint(5, 10)):
        origine, destinataire = rng.sample(cles, 2)  # sample => origine != destinataire
        # ~20 % de gros montants pour avoir des flags à vérifier
        if rng.random() < 0.2:
            montant = rng.uniform(SEUIL_FLAG + 1, 15000)
        else:
            montant = rng.uniform(10, 4000)
        date = debut + timedelta(minutes=rng.randint(0, 60 * 24 * 30))
        transactions.append(creer_transaction(date, origine, destinataire, round(montant, 2)))
    transactions.sort(key=lambda t: t["datetime_transaction"])
    return transactions


def ecrire_csv(chemin: Path, transactions: list[dict]) -> None:
    with chemin.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLONNES)
        writer.writeheader()
        writer.writerows(transactions)


def main() -> None:
    parser = argparse.ArgumentParser(description="Génère des CSV de transactions.")
    parser.add_argument("--nb-fichiers", type=int, default=3)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dossier", default="data")
    args = parser.parse_args()

    dossier = Path(args.dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)  # générateur isolé avec graine fixe

    ecrire_csv(dossier / "transactions_reference.csv", transactions_reference())
    for i in range(1, args.nb_fichiers + 1):
        ecrire_csv(dossier / f"transactions_{i:03d}.csv", transactions_aleatoires(rng))

    print(f"{args.nb_fichiers + 1} fichiers CSV générés dans '{dossier}/'")


if __name__ == "__main__":
    main()