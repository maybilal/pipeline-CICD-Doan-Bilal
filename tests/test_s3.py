"""
Tests du NIVEAU 2 : la pipeline lit les fichiers depuis le S3.

⚠️ Ces tests ont besoin que le service S3 tourne (docker compose up -d).
Ils utilisent un bucket à part, "test-pipeline", pour ne pas toucher aux
vrais fichiers du bucket "transactions".
"""
from decimal import Decimal
from pathlib import Path

import pytest

from src.pipeline.pipeline import executer_pipeline, fichiers_s3
from src.pipeline.retry import EchecDefinitif
from src.pipeline.stockage_s3 import (
    attendre_s3,
    client_s3,
    creer_bucket,
    envoyer_fichier,
    lister_objets,
    recuperer_fichier,
    simuler_pannes_s3,
)
from tests.outils import REFERENCE, base_vide, lire

BUCKET_TEST = "test-pipeline"


@pytest.fixture
def s3():
    """Un bucket de test qui ne contient que le fichier de référence."""
    client = client_s3()
    attendre_s3(client)
    creer_bucket(client, BUCKET_TEST)
    for nom in lister_objets(client, BUCKET_TEST):          # on vide le bucket de test
        client.delete_object(Bucket=BUCKET_TEST, Key=nom)
    envoyer_fichier(client, Path(REFERENCE), BUCKET_TEST)
    yield client
    simuler_pannes_s3(0)


# --- Envoi et lecture ----------------------------------------------------------

def test_le_fichier_envoye_est_present_dans_s3(s3):
    assert lister_objets(s3, BUCKET_TEST) == {
        "transactions_reference.csv": Path(REFERENCE).stat().st_size
    }


def test_le_fichier_recupere_est_identique_a_l_original(s3):
    contenu = recuperer_fichier(s3, "transactions_reference.csv", BUCKET_TEST, attente=0)
    assert contenu == Path(REFERENCE).read_bytes()


def test_pipeline_complete_depuis_s3(s3):
    conn = base_vide()
    try:
        bilan = executer_pipeline(fichiers_s3(s3, BUCKET_TEST, attente=0), attente=0)

        assert bilan["traites"] == ["transactions_reference.csv"]
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(6,)]
        assert lire(conn, "SELECT total FROM somme_envoyee_par_banque WHERE banque = 'BNP Paribas'") \
            == [(Decimal("17300.01"),)]

        # Relancer : le fichier du S3 est reconnu comme déjà traité
        bilan = executer_pipeline(fichiers_s3(s3, BUCKET_TEST, attente=0), attente=0)
        assert bilan["ignores"] == ["transactions_reference.csv"]
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(6,)]
    finally:
        conn.close()


# --- Retry lors de la récupération ----------------------------------------------

def test_recuperation_reussit_apres_deux_pannes(s3):
    simuler_pannes_s3(2)
    contenu = recuperer_fichier(s3, "transactions_reference.csv", BUCKET_TEST,
                                max_tentatives=3, attente=0)
    assert contenu == Path(REFERENCE).read_bytes()


def test_fichier_inaccessible_arrete_le_traitement_proprement(s3):
    conn = base_vide()
    try:
        simuler_pannes_s3(5)         # plus de pannes que de tentatives autorisées (3)
        with pytest.raises(EchecDefinitif):
            executer_pipeline(fichiers_s3(s3, BUCKET_TEST, max_tentatives=3, attente=0), attente=0)

        # Rien n'a été inséré, et le fichier n'est pas marqué comme traité :
        # il sera traité au prochain lancement, quand le S3 répondra.
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(0,)]
        assert lire(conn, "SELECT COUNT(*) FROM processed_files") == [(0,)]
    finally:
        conn.close()
