"""
BASE DE DONNÉES : créer les tables et y enregistrer les résultats.

Les informations de connexion sont lues dans des "variables d'environnement",
avec des valeurs par défaut qui correspondent au docker-compose.yml.
Ça permet à la pipeline CI (GitHub Actions) d'utiliser d'autres valeurs
sans modifier le code.
"""
import os
from pathlib import Path

import psycopg2

SCHEMA = Path(__file__).resolve().parents[2] / "sql" / "schema.sql"


def connexion():
    """Ouvre une connexion à PostgreSQL."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER", "pipeline"),
        password=os.getenv("DB_PASSWORD", "pipeline"),
        dbname=os.getenv("DB_NAME", "transactions"),
    )


def creer_tables(conn) -> None:
    """Exécute schema.sql pour créer les tables (si elles n'existent pas déjà)."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


# --- Simulation de pannes (étape 7) -----------------------------------------
# SIMULER_PANNES_BDD=2 python main.py  => les 2 premières insertions échouent.
_pannes_restantes = int(os.getenv("SIMULER_PANNES_BDD", "0"))


def simuler_pannes(nombre: int) -> None:
    """Programme `nombre` pannes à venir (utilisé par les tests)."""
    global _pannes_restantes
    _pannes_restantes = nombre


def _panne_eventuelle() -> None:
    global _pannes_restantes
    if _pannes_restantes > 0:
        _pannes_restantes -= 1
        raise psycopg2.OperationalError(
            "[SIMULATION] connexion perdue : base de données temporairement indisponible"
        )


# --- Fichiers déjà traités ---------------------------------------------------
def fichier_deja_traite(conn, empreinte: str) -> bool:
    """Ce contenu de fichier a-t-il déjà été traité avec succès ?"""
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM processed_files WHERE empreinte = %s", (empreinte,))
        return cur.fetchone() is not None


# --- Insertion ----------------------------------------------------------------
def lister_comptes(transactions: list[dict]) -> dict:
    """
    Construit la liste des comptes : {iban: (pays, banque)}.
    Le CSV ne donne pas la banque du DESTINATAIRE : on met "Inconnue",
    sauf si ce compte apparaît aussi comme émetteur (là, on connaît sa banque).
    """
    comptes = {}
    for t in transactions:
        comptes.setdefault(t["iban_destinataire"], (t["pays_destinataire"], "Inconnue"))
    for t in transactions:
        comptes[t["iban_origine"]] = (t["pays_source"], t["banque_source"])
    return comptes


def inserer_resultats(conn, nom_fichier: str, empreinte: str, transactions_flaguees: list[dict],
                      envoye_iban: dict, recu_iban: dict, envoye_banque: dict) -> None:
    """
    Enregistre les comptes, les transactions, les totaux ET le fichier dans
    processed_files.

    Tout est fait dans UNE SEULE transaction SQL : soit tout est enregistré,
    soit rien. C'est ce qui garantit l'absence de doublons même avec le retry :
      - si ça échoue au milieu, rien n'est gardé, et le fichier n'est pas marqué
        "traité" => le retry recommence proprement ;
      - si ça réussit, le fichier est marqué "traité" en même temps que ses
        données => il ne sera plus jamais retraité.
    """
    try:
        with conn.cursor() as cur:
            # 1. Les comptes (on complète une banque "Inconnue" si on l'apprend)
            for iban, (pays, banque) in lister_comptes(transactions_flaguees).items():
                cur.execute(
                    "INSERT INTO comptes (iban, pays, banque) VALUES (%s, %s, %s) "
                    "ON CONFLICT (iban) DO UPDATE SET banque = EXCLUDED.banque "
                    "WHERE comptes.banque = 'Inconnue'",
                    (iban, pays, banque),
                )

            # 2. Les transactions
            for t in transactions_flaguees:
                cur.execute(
                    "INSERT INTO transactions (datetime_transaction, iban_origine, "
                    "iban_destinataire, montant, flag) VALUES (%s, %s, %s, %s, %s)",
                    (t["datetime_transaction"], t["iban_origine"],
                     t["iban_destinataire"], t["montant"], t["flag"]),
                )

            # Panne simulée EN PLEIN MILIEU : les transactions viennent d'être
            # insérées... le rollback doit les annuler.
            _panne_eventuelle()

            # 3. Les totaux (on ajoute au total existant)
            for table, cle, sommes in (
                ("somme_envoyee_par_iban", "iban", envoye_iban),
                ("somme_recue_par_iban", "iban", recu_iban),
                ("somme_envoyee_par_banque", "banque", envoye_banque),
            ):
                for valeur, total in sommes.items():
                    cur.execute(
                        f"INSERT INTO {table} ({cle}, total) VALUES (%s, %s) "
                        f"ON CONFLICT ({cle}) DO UPDATE SET total = {table}.total + EXCLUDED.total",
                        (valeur, total),
                    )

            # 4. Le fichier est marqué comme traité
            cur.execute(
                "INSERT INTO processed_files (nom_fichier, empreinte, nb_transactions) "
                "VALUES (%s, %s, %s)",
                (nom_fichier, empreinte, len(transactions_flaguees)),
            )
        conn.commit()      # tout s'est bien passé : on valide TOUT
    except Exception:
        conn.rollback()    # un problème : on annule TOUT
        raise
