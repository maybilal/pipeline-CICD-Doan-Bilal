"""
La pipeline complète. Pour chaque fichier :

    S3 -> récupération -> chargement -> validation -> traitement -> base de données

Le chargement dépend du FORMAT du fichier (Niveau 3) :
    .csv           -> lecture du CSV
    .png / .jpg    -> OCR + extraction des informations
    .txt           -> SLM (petit modèle de langage)
Ensuite, tous les formats suivent EXACTEMENT le même chemin.

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
from src.pipeline.ocr import transactions_depuis_image
from src.pipeline.retry import avec_retry
from src.pipeline.slm import transactions_depuis_texte
from src.pipeline.stockage_s3 import BUCKET, lister_objets, recuperer_fichier
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)
from src.pipeline.validation import DonneeInvalide, valider_transactions

# Un fichier à traiter = (son nom, une fonction qui renvoie son contenu)
FichierATraiter = tuple[str, Callable[[], bytes]]

# Pour chaque format accepté : la fonction qui en extrait les transactions
CHARGEURS = {
    ".csv": lambda contenu: lire_csv(contenu.decode("utf-8")),
    ".png": transactions_depuis_image,
    ".jpg": transactions_depuis_image,
    ".jpeg": transactions_depuis_image,
    ".txt": transactions_depuis_texte,
}


def format_accepte(nom: str) -> bool:
    return Path(nom).suffix.lower() in CHARGEURS


def charger(nom: str, contenu: bytes) -> list[dict]:
    """Choisit la bonne façon de lire le fichier selon son extension."""
    return CHARGEURS[Path(nom).suffix.lower()](contenu)


# --- D'où viennent les fichiers ----------------------------------------------

def fichiers_s3(s3, bucket: str = BUCKET, max_tentatives: int = 3,
                attente: float = 1.0) -> list[FichierATraiter]:
    """Les fichiers acceptés (CSV, images, textes) présents dans le bucket S3."""
    noms = sorted(n for n in lister_objets(s3, bucket) if format_accepte(n))
    return [
        (nom, lambda nom=nom: recuperer_fichier(s3, nom, bucket, max_tentatives, attente))
        for nom in noms
    ]


def fichiers_locaux(source: str | Path) -> list[FichierATraiter]:
    """Des fichiers lus sur le disque (utilisé par les tests)."""
    source = Path(source)
    chemins = [source] if source.is_file() else sorted(
        c for c in source.iterdir() if format_accepte(c.name))
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

    # 2. CHARGEMENT (selon le format), 3. VALIDATION, 4. TRAITEMENT
    transactions = valider_transactions(charger(nom, contenu), nom)
    signature = empreinte(contenu)
    resultats = (
        ajouter_flags(transactions),
        somme_envoyee_par_iban(transactions),
        somme_recue_par_iban(transactions),
        somme_envoyee_par_banque(transactions),
    )

    # 5. BASE DE DONNÉES : une "tentative" complète, que le retry peut rejouer.
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
    """
    Traite une liste de fichiers, l'un après l'autre. Renvoie le bilan.
    Un fichier invalide est REJETÉ (rien n'est inséré) sans bloquer les autres.
    """
    bilan = {"traites": [], "ignores": [], "rejetes": []}
    for nom, recuperer in fichiers:
        try:
            insere = traiter_fichier(nom, recuperer, connecter, max_tentatives, attente)
        except DonneeInvalide as erreur:
            print(f"❌ {nom} : REJETÉ, {erreur}")
            bilan["rejetes"].append(nom)
            continue
        if insere:
            print(f"✅ {nom} : traité et inséré")
            bilan["traites"].append(nom)
        else:
            print(f"⏭️  {nom} : déjà traité, ignoré")
            bilan["ignores"].append(nom)
    return bilan