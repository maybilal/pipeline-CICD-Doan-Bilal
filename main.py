"""
Point d'entrée : CHARGEMENT -> TRAITEMENT -> BASE DE DONNÉES.

Usage :
    python main.py               # traite tous les CSV du dossier data/
    python main.py chemin/fichier.csv
"""
import sys
from pathlib import Path

from src.pipeline.base_de_donnees import connexion, creer_tables, inserer_resultats
from src.pipeline.chargement import charger_csv, charger_dossier
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)


def afficher(titre: str, sommes: dict) -> None:
    print(f"\n{titre}")
    for cle, total in sorted(sommes.items(), key=lambda x: -x[1]):
        print(f"  {cle:<30} {total:>12}")


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")

    # 1. CHARGEMENT (va chercher les données)
    transactions = charger_csv(source) if source.is_file() else charger_dossier(source)
    print(f"{len(transactions)} transactions chargées depuis {source}")

    # 2. TRAITEMENT (calculs purs)
    envoye = somme_envoyee_par_iban(transactions)
    recu = somme_recue_par_iban(transactions)
    par_banque = somme_envoyee_par_banque(transactions)
    avec_flags = ajouter_flags(transactions)

    afficher("Somme envoyée par IBAN :", envoye)
    afficher("Somme envoyée par banque :", par_banque)
    afficher("Somme reçue par IBAN :", recu)

    # Vérification de bon sens : tout ce qui est envoyé est forcément reçu.
    total_envoye, total_recu = sum(envoye.values()), sum(recu.values())
    print(f"\nTotal envoyé : {total_envoye}   |   Total reçu : {total_recu}")
    print("Cohérent ✅" if total_envoye == total_recu else "INCOHÉRENT ❌")

    flaguees = [t for t in avec_flags if t["flag"]]
    print(f"\nTransactions flaguées (> 5000) : {len(flaguees)}")
    for t in flaguees:
        print(f"  {t['datetime_transaction']}  {t['iban_origine']}  {t['montant']}")

    # 3. BASE DE DONNÉES (enregistrement durable des résultats)
    conn = connexion()
    try:
        creer_tables(conn)
        inserer_resultats(conn, avec_flags, envoye, recu, par_banque)
        print(f"\n✅ {len(avec_flags)} transactions enregistrées dans la base.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()