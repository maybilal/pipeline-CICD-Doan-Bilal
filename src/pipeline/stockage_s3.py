"""
STOCKAGE S3 : se connecter au service S3, créer le bucket, envoyer, lister
et récupérer des fichiers.

Comme pour la base de données, les informations de connexion sont lues dans
des variables d'environnement, avec des valeurs par défaut qui correspondent
au docker-compose.yml.
"""
import os
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)

from src.pipeline.retry import avec_retry

BUCKET = os.getenv("S3_BUCKET", "transactions")


def client_s3():
    """
    Crée un "client" S3 : l'objet Python qui sait parler au service S3.
    boto3 est la librairie officielle d'Amazon pour S3 ; elle fonctionne avec
    n'importe quel service compatible (RustFS, SeaweedFS, Garage...) : il suffit
    de lui donner l'adresse du service (endpoint_url).
    """
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT", "http://localhost:9000"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY", "pipeline-access"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY", "pipeline-secret-123"),
        region_name="us-east-1",                 # obligatoire pour boto3, ignoré en local
        config=Config(
            s3={"addressing_style": "path"},     # adresse du type http://hote/bucket/fichier
            connect_timeout=3, read_timeout=10,  # au-delà, on considère que c'est un "timeout"
            retries={"max_attempts": 1},         # c'est NOTRE retry qui gère les nouvelles tentatives
        ),
    )


def attendre_s3(s3, max_tentatives: int = 6) -> None:
    """
    Le service S3 met quelques secondes à démarrer : on attend qu'il réponde,
    en réutilisant le mécanisme de retry de l'étape 7.
    """
    avec_retry(
        s3.list_buckets,
        description="la connexion au service S3",
        erreurs_temporaires=(EndpointConnectionError, ConnectionError, ClientError),
        max_tentatives=max_tentatives,
        attente_initiale=1,
    )
    print("✅ Service S3 joignable")


def creer_bucket(s3, bucket: str = BUCKET) -> None:
    """Crée le bucket s'il n'existe pas encore (sinon, ne fait rien)."""
    existants = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if bucket in existants:
        print(f"✅ Bucket '{bucket}' déjà existant")
    else:
        s3.create_bucket(Bucket=bucket)
        print(f"✅ Bucket '{bucket}' créé")


def envoyer_fichier(s3, chemin: Path, bucket: str = BUCKET) -> None:
    """Envoie UN fichier dans le bucket. Son nom dans S3 = son nom de fichier."""
    s3.upload_file(str(chemin), bucket, chemin.name)


def lister_objets(s3, bucket: str = BUCKET) -> dict:
    """Renvoie les fichiers présents dans le bucket : {nom: taille en octets}."""
    reponse = s3.list_objects_v2(Bucket=bucket)
    return {o["Key"]: o["Size"] for o in reponse.get("Contents", [])}


# --- Récupération d'un fichier, avec retry (Niveau 2, étape 4) ---------------

class S3TemporairementIndisponible(Exception):
    """Erreur utilisée pour SIMULER une panne du S3."""


# Les erreurs considérées comme TEMPORAIRES : ça vaut la peine de réessayer.
ERREURS_TEMPORAIRES_S3 = (
    EndpointConnectionError,      # service S3 injoignable (arrêté, redémarrage...)
    ConnectTimeoutError,          # trop long pour se connecter
    ReadTimeoutError,             # trop long pour recevoir le fichier (timeout)
    ConnectionClosedError,        # connexion coupée en cours de route (erreur réseau)
    S3TemporairementIndisponible, # panne simulée
)

# SIMULER_PANNES_S3=2 python main.py  => les 2 premières récupérations échouent.
_pannes_s3_restantes = int(os.getenv("SIMULER_PANNES_S3", "0"))


def simuler_pannes_s3(nombre: int) -> None:
    """Programme `nombre` pannes de récupération à venir (utilisé par les tests)."""
    global _pannes_s3_restantes
    _pannes_s3_restantes = nombre


def _telecharger(s3, nom: str, bucket: str) -> bytes:
    """UNE tentative de récupération du contenu d'un fichier."""
    global _pannes_s3_restantes
    if _pannes_s3_restantes > 0:
        _pannes_s3_restantes -= 1
        raise S3TemporairementIndisponible(
            "[SIMULATION] timeout : le service S3 ne répond pas"
        )
    return s3.get_object(Bucket=bucket, Key=nom)["Body"].read()


def recuperer_fichier(s3, nom: str, bucket: str = BUCKET,
                      max_tentatives: int = 3, attente: float = 1.0) -> bytes:
    """
    Récupère le contenu d'un fichier du S3, en réessayant en cas de panne
    temporaire. Lève EchecDefinitif si le fichier reste inaccessible.
    """
    return avec_retry(
        lambda: _telecharger(s3, nom, bucket),
        description=f"la récupération de {nom} depuis S3",
        erreurs_temporaires=ERREURS_TEMPORAIRES_S3,
        max_tentatives=max_tentatives,
        attente_initiale=attente,
    )
