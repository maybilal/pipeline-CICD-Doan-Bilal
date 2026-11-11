"""
CHARGEMENT des données : lire les fichiers CSV et les transformer en
données Python utilisables.

Ce fichier ne fait AUCUN calcul. Son seul rôle : aller chercher les données.
"""
import csv
from decimal import Decimal
from pathlib import Path


def charger_csv(chemin: str | Path) -> list[dict]:
    """
    Lit UN fichier CSV et renvoie une liste de transactions.
    Chaque transaction est un dictionnaire, par exemple :
        {"iban_origine": "FR76...", "montant": Decimal("100.00"), ...}
    """
    transactions = []
    with open(chemin, newline="", encoding="utf-8") as f:
        for ligne in csv.DictReader(f):
            # Dans un CSV, tout est du texte : "100.00" n'est pas un nombre.
            # On le convertit en Decimal, un type fait pour l'argent
            # (voir l'explication sur les arrondis).
            ligne["montant"] = Decimal(ligne["montant"])
            transactions.append(ligne)
    return transactions


def charger_dossier(dossier: str | Path) -> list[dict]:
    """Lit TOUS les fichiers .csv d'un dossier et regroupe leurs transactions."""
    transactions = []
    for chemin in sorted(Path(dossier).glob("*.csv")):
        transactions.extend(charger_csv(chemin))
    return transactions