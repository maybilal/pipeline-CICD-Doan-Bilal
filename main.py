"""
Point d'entrée : lance la pipeline puis affiche le contenu de la base.

Usage :
    python main.py                    # traite les nouveaux CSV du dossier data/
    python main.py chemin/fichier.csv
    SIMULER_PANNES_BDD=2 python main.py   # simule 2 pannes temporaires de la base
"""
import sys

from src.pipeline.base_de_donnees import connexion
from src.pipeline.pipeline import executer_pipeline
from src.pipeline.retry import EchecDefinitif


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
    source = sys.argv[1] if len(sys.argv) > 1 else "data"
    try:
        bilan = executer_pipeline(source)
    except EchecDefinitif as erreur:
        print(f"\n🛑 PIPELINE ARRÊTÉE : {erreur}")
        sys.exit(1)       # code d'erreur => la pipeline GitHub passe au ROUGE

    print(f"\nBilan : {len(bilan['traites'])} fichier(s) traité(s), "
          f"{len(bilan['ignores'])} ignoré(s) car déjà traité(s).")
    afficher_base()


if __name__ == "__main__":
    main()