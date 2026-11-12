"""
Point d'entrée : traite les nouveaux fichiers du bucket S3, puis affiche le
contenu de la base.

    S3 -> récupération -> chargement -> traitement -> base de données

Usage :
    python main.py
    SIMULER_PANNES_BDD=2 python main.py   # simule 2 pannes temporaires de la base
    SIMULER_PANNES_S3=2 python main.py    # simule 2 pannes lors de la récupération S3
(Sous Windows PowerShell :  $env:SIMULER_PANNES_S3=2; python main.py; $env:SIMULER_PANNES_S3=0)
"""
import sys

from src.pipeline.base_de_donnees import connexion
from src.pipeline.pipeline import executer_pipeline, fichiers_s3
from src.pipeline.retry import EchecDefinitif
from src.pipeline.stockage_s3 import BUCKET, attendre_s3, client_s3


def lire(conn, requete: str) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(requete)
        return cur.fetchall()


def afficher_base() -> None:
    """Affiche l'état de la base (tous fichiers traités confondus)."""
    conn = connexion()
    try:
        for titre, table, cle in (
            ("Somme envoyée par IBAN", "somme_envoyee_par_iban", "iban"),
            ("Somme envoyée par banque", "somme_envoyee_par_banque", "banque"),
            ("Somme reçue par IBAN", "somme_recue_par_iban", "iban"),
        ):
            print(f"\n{titre} :")
            for valeur, total in lire(conn, f"SELECT {cle}, total FROM {table} ORDER BY total DESC"):
                print(f"  {valeur:<30} {total:>12}")

        (envoye,), = lire(conn, "SELECT COALESCE(SUM(total), 0) FROM somme_envoyee_par_iban")
        (recu,), = lire(conn, "SELECT COALESCE(SUM(total), 0) FROM somme_recue_par_iban")
        print(f"\nTotal envoyé : {envoye}   |   Total reçu : {recu}")
        print("Cohérent ✅" if envoye == recu else "INCOHÉRENT ❌")

        (nb,), = lire(conn, "SELECT COUNT(*) FROM transactions")
        (nb_flags,), = lire(conn, "SELECT COUNT(*) FROM transactions WHERE flag")
        (nb_fichiers,), = lire(conn, "SELECT COUNT(*) FROM processed_files")
        print(f"\nDans la base : {nb} transactions ({nb_flags} flaguées), "
              f"issues de {nb_fichiers} fichiers traités.")
    finally:
        conn.close()


def main() -> None:
    try:
        s3 = client_s3()
        attendre_s3(s3)
        fichiers = fichiers_s3(s3)
        print(f"📦 {len(fichiers)} fichier(s) (CSV, images ou textes) trouvé(s) dans le bucket '{BUCKET}'\n")
        bilan = executer_pipeline(fichiers)
    except EchecDefinitif as erreur:
        # Rien n'est perdu : les fichiers déjà insérés le restent, et ceux qui
        # n'ont pas pu l'être seront retraités au prochain lancement.
        print(f"\n🛑 PIPELINE ARRÊTÉE : {erreur}")
        sys.exit(1)       # code d'erreur => la pipeline GitHub passe au ROUGE

    print(f"\nBilan : {len(bilan['traites'])} fichier(s) traité(s), "
          f"{len(bilan['ignores'])} ignoré(s) car déjà traité(s), "
          f"{len(bilan['rejetes'])} rejeté(s) car invalide(s).")
    afficher_base()

    if bilan["rejetes"]:
        # Des données invalides ont été détectées : on le signale à la CI.
        print(f"\n⚠️  Fichiers rejetés à corriger : {', '.join(bilan['rejetes'])}")
        sys.exit(1)


if __name__ == "__main__":
    main()