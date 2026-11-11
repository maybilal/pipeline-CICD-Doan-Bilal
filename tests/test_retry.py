"""
Tests du mécanisme de RETRY (étape 7).
"""
from decimal import Decimal

import pytest

from src.pipeline.base_de_donnees import simuler_pannes
from src.pipeline.pipeline import executer_pipeline
from src.pipeline.retry import EchecDefinitif, avec_retry
from tests.outils import REFERENCE, base_vide, lire


class ErreurTemporaire(Exception):
    pass


# --- Le mécanisme seul (sans base de données) --------------------------------

def test_reussit_apres_deux_echecs():
    appels = []

    def fonction():
        appels.append(1)
        if len(appels) < 3:
            raise ErreurTemporaire("panne")
        return "ok"

    resultat = avec_retry(fonction, "le test", (ErreurTemporaire,), max_tentatives=3, attente_initiale=0)
    assert resultat == "ok"
    assert len(appels) == 3          # 2 échecs + 1 réussite


def test_abandonne_apres_le_nombre_maximal_de_tentatives():
    appels = []

    def toujours_en_panne():
        appels.append(1)
        raise ErreurTemporaire("panne")

    with pytest.raises(EchecDefinitif):
        avec_retry(toujours_en_panne, "le test", (ErreurTemporaire,), max_tentatives=3, attente_initiale=0)
    assert len(appels) == 3          # pas une tentative de plus


def test_une_erreur_non_temporaire_n_est_pas_reessayee():
    appels = []

    def donnee_invalide():
        appels.append(1)
        raise ValueError("montant invalide")

    with pytest.raises(ValueError):
        avec_retry(donnee_invalide, "le test", (ErreurTemporaire,), max_tentatives=3, attente_initiale=0)
    assert len(appels) == 1          # réessayer ne servirait à rien


# --- Avec la vraie base : pannes simulées pendant l'insertion ----------------

def test_pannes_temporaires_puis_succes_sans_doublon():
    conn = base_vide()
    try:
        simuler_pannes(2)            # les 2 premières insertions échouent EN PLEIN MILIEU
        bilan = executer_pipeline(REFERENCE, attente=0)

        assert bilan["traites"] == ["transactions_reference.csv"]
        # Les tentatives ratées ont été annulées (rollback) : pas de transactions en double
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(6,)]
        assert lire(conn, "SELECT COUNT(*) FROM processed_files") == [(1,)]
        assert lire(conn, "SELECT total FROM somme_envoyee_par_banque WHERE banque = 'BNP Paribas'") \
            == [(Decimal("17300.01"),)]
    finally:
        simuler_pannes(0)
        conn.close()


def test_trop_de_pannes_arrete_la_pipeline_sans_rien_inserer():
    conn = base_vide()
    try:
        simuler_pannes(5)            # plus de pannes que de tentatives autorisées (3)
        with pytest.raises(EchecDefinitif):
            executer_pipeline(REFERENCE, attente=0)

        # Rien n'a été gardé, et le fichier n'est PAS marqué comme traité :
        # il sera bien traité au prochain lancement.
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(0,)]
        assert lire(conn, "SELECT COUNT(*) FROM processed_files") == [(0,)]
    finally:
        simuler_pannes(0)
        conn.close()