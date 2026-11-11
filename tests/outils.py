"""Petits outils partagés par les tests."""
from src.pipeline.base_de_donnees import connexion, creer_tables

REFERENCE = "tests/donnees/transactions_reference.csv"

# Les 4 comptes du fichier de référence
A = "FR7630001007941234567890185"
B = "FR7630004000031234567890143"
C = "DE89370400440532013000"
D = "DE44500105175407324931"


def base_vide():
    """Ouvre une connexion sur une base dont toutes les tables ont été vidées."""
    conn = connexion()
    creer_tables(conn)
    with conn.cursor() as cur:
        cur.execute("TRUNCATE transactions, somme_envoyee_par_iban, somme_recue_par_iban, "
                    "somme_envoyee_par_banque, comptes, processed_files "
                    "RESTART IDENTITY CASCADE")
    conn.commit()
    return conn


def lire(conn, requete: str) -> list[tuple]:
    """Exécute une requête SQL et renvoie les lignes."""
    with conn.cursor() as cur:
        cur.execute(requete)
        return cur.fetchall()