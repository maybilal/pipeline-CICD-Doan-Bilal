"""
Point d'entrée : lance la pipeline et affiche les résultats.

Usage :
    python main.py               # traite tous les CSV du dossier data/
    python main.py chemin/fichier.csv
"""
import sys

from src.pipeline.base_de_donnees import connexion
from src.pipeline.pipeline import executer_pipeline


def afficher(titre: str, sommes: dict) -> None:
    print(f"\n{titre}")
    for cle, total in sorted(sommes.items(), key=lambda x: -x[1]):
        print(f"  {cle:<30} {total:>12}")


def main() -> None:
    source = sys.argv[1] if len(sys.argv) > 1 else "data"

    conn = connexion()
    try:
        r = executer_pipeline(source, conn)
    finally:
        conn.close()

    print(f"{len(r['transactions'])} transactions chargées depuis {source}")
    afficher("Somme envoyée par IBAN :", r["envoye_iban"])
    afficher("Somme envoyée par banque :", r["envoye_banque"])
    afficher("Somme reçue par IBAN :", r["recu_iban"])

    # Vérification de bon sens : tout ce qui est envoyé est forcément reçu.
    total_envoye, total_recu = sum(r["envoye_iban"].values()), sum(r["recu_iban"].values())
    print(f"\nTotal envoyé : {total_envoye}   |   Total reçu : {total_recu}")
    print("Cohérent ✅" if total_envoye == total_recu else "INCOHÉRENT ❌")

    flaguees = [t for t in r["transactions"] if t["flag"]]
    print(f"\nTransactions flaguées (> 5000) : {len(flaguees)}")
    for t in flaguees:
        print(f"  {t['datetime_transaction']}  {t['iban_origine']}  {t['montant']}")

    print(f"\n✅ {len(r['transactions'])} transactions enregistrées dans la base.")


if __name__ == "__main__":
    main()