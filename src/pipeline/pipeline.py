"""
La pipeline complète. Pour chaque fichier :

    S3 -> récupération du fichier -> chargement -> traitement -> base de données

- Un fichier déjà traité est ignoré (empreinte dans processed_files).
- La récupération depuis S3 ET l'insertion en base sont protégées par un retry.

Le code ne dépend PAS de l'endroit où sont rangés les fichiers : on lui donne
une liste de "fichiers à traiter", chacun avec une fonction qui sait aller
chercher son contenu. Les fichiers viennent du S3 en temps normal, et du
disque dans certains tests.
"""
import hashlib
from pathlib import Path
from typing import Callable

import psycopg2

from src.pipeline.base_de_donnees import (
    connexion,
    creer_tables,
    fichier_deja_traite,
    inserer_resultats,
)
from src.pipeline.chargement import lire_csv
from src.pipeline.retry import avec_retry
from src.pipeline.stockage_s3 import BUCKET, lister_objets, recuperer_fichier
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)

# Un fichier à traiter = (son nom, une fonction qui renvoie son contenu)
FichierATraiter = tuple[str, Callable[[], bytes]]


# --- D'où viennent les fichiers ----------------------------------------------

def fichiers_s3(s3, bucket: str = BUCKET, max_tentatives: int = 3,
                attente: float = 1.0) -> list[FichierATraiter]:
    """Les fichiers .csv présents dans le bucket S3 (source normale)."""
    noms = sorted(n for n in lister_objets(s3, bucket) if n.endswith(".csv"))
    return [
        (nom, lambda nom=nom: recuperer_fichier(s3, nom, bucket, max_tentatives, attente))
        for nom in noms
    ]


def fichiers_locaux(source: str | Path) -> list[FichierATraiter]:
    """Des fichiers lus sur le disque (utilisé par les tests)."""
    source = Path(source)
    chemins = [source] if source.is_file() else sorted(source.glob("*.csv"))
    return [(c.name, c.read_bytes) for c in chemins]


# --- Le traitement -------------------------------------------------------------

def empreinte(contenu: bytes) -> str:
    """
    Empreinte SHA-256 du CONTENU : une suite de 64 caractères qui change
    complètement si un seul caractère du fichier change.
    """
    return hashlib.sha256(contenu).hexdigest()


def traiter_fichier(nom: str, recuperer: Callable[[], bytes], connecter=connexion,
                    max_tentatives: int = 3, attente: float = 1.0) -> bool:
    """
    Traite UN fichier. Renvoie True s'il a été inséré, False s'il était déjà traité.
    """
    # 1. RÉCUPÉRATION du fichier (avec retry s'il vient du S3)
    contenu = recuperer()

    # 2. CHARGEMENT et 3. TRAITEMENT (pas de S3 ni de base de données ici)
    transactions = lire_csv(contenu.decode("utf-8"))
    signature = empreinte(contenu)
    resultats = (
        ajouter_flags(transactions),
        somme_envoyee_par_iban(transactions),
        somme_recue_par_iban(transactions),
        somme_envoyee_par_banque(transactions),
    )

    # 4. BASE DE DONNÉES : une "tentative" complète, que le retry peut rejouer.
    def tentative() -> bool:
        conn = connecter()            # nouvelle connexion à chaque tentative
        try:
            creer_tables(conn)
            if fichier_deja_traite(conn, signature):
                return False          # déjà fait : on ne touche à rien
            inserer_resultats(conn, nom, signature, *resultats)
            return True
        finally:
            conn.close()

    return avec_retry(
        tentative,
        description=f"l'insertion de {nom}",
        erreurs_temporaires=(psycopg2.OperationalError,),   # erreurs de connexion
        max_tentatives=max_tentatives,
        attente_initiale=attente,
    )


def executer_pipeline(fichiers: list[FichierATraiter], connecter=connexion,
                      max_tentatives: int = 3, attente: float = 1.0) -> dict:
    """Traite une liste de fichiers, l'un après l'autre. Renvoie le bilan."""
    bilan = {"traites": [], "ignores": []}
    for nom, recuperer in fichiers:
        if traiter_fichier(nom, recuperer, connecter, max_tentatives, attente):
            print(f"✅ {nom} : traité et inséré")
            bilan["traites"].append(nom)
        else:
            print(f"⏭️  {nom} : déjà traité, ignoré")
            bilan["ignores"].append(nom)
    return bilan
