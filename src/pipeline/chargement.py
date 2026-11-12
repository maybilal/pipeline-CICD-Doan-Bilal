"""
CHARGEMENT des données : transformer le contenu d'un fichier CSV en
données Python utilisables.

Ce fichier ne fait AUCUN calcul. Son seul rôle : lire les données.
Il ne sait pas d'où vient le fichier (disque ou S3) : on lui donne le texte.
"""
import csv
import io
from decimal import Decimal
from pathlib import Path


def lire_csv(texte: str) -> list[dict]:
    """
    Transforme le TEXTE d'un fichier CSV en liste de transactions.
    Chaque transaction est un dictionnaire, par exemple :
        {"iban_origine": "FR76...", "montant": Decimal("100.00"), ...}
    """
    transactions = []
    for ligne in csv.DictReader(io.StringIO(texte)):
        # Dans un CSV, tout est du texte : "100.00" n'est pas un nombre.
        # On le convertit en Decimal, un type fait pour l'argent.
        ligne["montant"] = Decimal(ligne["montant"])
        transactions.append(ligne)
    return transactions


def charger_csv(chemin: str | Path) -> list[dict]:
    """Lit un fichier CSV depuis le disque (utilisé par les tests)."""
    return lire_csv(Path(chemin).read_text(encoding="utf-8"))
