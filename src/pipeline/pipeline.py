"""
La pipeline complète en UNE fonction : charger -> traiter -> insérer.

main.py l'utilise pour le vrai traitement, et les tests l'utilisent aussi :
on teste donc exactement le même code que celui qui tourne "en vrai".
"""
from pathlib import Path

from src.pipeline.base_de_donnees import creer_tables, inserer_resultats
from src.pipeline.chargement import charger_csv, charger_dossier
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)


def executer_pipeline(source: str | Path, conn) -> dict:
    """Traite un fichier (ou un dossier) et insère les résultats dans la base."""
    source = Path(source)

    # 1. CHARGEMENT
    transactions = charger_csv(source) if source.is_file() else charger_dossier(source)

    # 2. TRAITEMENT
    resultats = {
        "transactions": ajouter_flags(transactions),
        "envoye_iban": somme_envoyee_par_iban(transactions),
        "recu_iban": somme_recue_par_iban(transactions),
        "envoye_banque": somme_envoyee_par_banque(transactions),
    }

    # 3. BASE DE DONNÉES
    creer_tables(conn)
    inserer_resultats(conn, resultats["transactions"], resultats["envoye_iban"],
                      resultats["recu_iban"], resultats["envoye_banque"])
    return resultats