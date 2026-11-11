"""
Tests d'INTÉGRATION : on fait tourner la VRAIE pipeline (CSV -> calculs -> PostgreSQL)
sur le fichier de référence, puis on va lire la base pour vérifier son contenu.

⚠️ Ces tests VIDENT les tables avant de commencer.
"""
from datetime import datetime
from decimal import Decimal

import pytest

from src.pipeline.pipeline import executer_pipeline
from tests.outils import REFERENCE, A, B, C, D, base_vide, lire


@pytest.fixture(scope="module")
def base():
    """
    Préparation commune à tous les tests de ce fichier (exécutée une seule fois) :
    base vide -> pipeline sur le fichier de référence -> on donne la connexion aux tests.
    """
    conn = base_vide()
    executer_pipeline(REFERENCE, attente=0)
    yield conn          # les tests s'exécutent ici
    conn.close()        # puis on ferme la connexion


# --- 1. Les données sont bien insérées --------------------------------------

def test_toutes_les_transactions_sont_inserees(base):
    assert lire(base, "SELECT COUNT(*) FROM transactions") == [(6,)]


def test_tous_les_comptes_sont_inseres(base):
    assert dict(lire(base, "SELECT iban, banque FROM comptes")) == {
        A: "BNP Paribas", B: "BNP Paribas", C: "Commerzbank", D: "Deutsche Bank",
    }


def test_le_fichier_est_enregistre_comme_traite(base):
    assert lire(base, "SELECT nom_fichier, nb_transactions FROM processed_files") == [
        ("transactions_reference.csv", 6)
    ]


# --- 2. Les valeurs enregistrées sont correctes -----------------------------

def test_valeurs_d_une_transaction(base):
    ligne = lire(base, "SELECT datetime_transaction, iban_origine, iban_destinataire, "
                       "montant FROM transactions WHERE id = 3")
    assert ligne == [(datetime(2026, 1, 15, 9, 20), B, C, Decimal("5000.01"))]


# --- 3. Les traitements produisent les résultats attendus -------------------

def test_somme_envoyee_par_iban_en_base(base):
    assert dict(lire(base, "SELECT iban, total FROM somme_envoyee_par_iban")) == {
        A: Decimal("12300.00"), B: Decimal("5000.01"),
        C: Decimal("250.50"), D: Decimal("49.50"),
    }


def test_somme_envoyee_par_banque_en_base(base):
    assert dict(lire(base, "SELECT banque, total FROM somme_envoyee_par_banque")) == {
        "BNP Paribas": Decimal("17300.01"),
        "Commerzbank": Decimal("250.50"),
        "Deutsche Bank": Decimal("49.50"),
    }


def test_somme_recue_par_iban_en_base(base):
    assert dict(lire(base, "SELECT iban, total FROM somme_recue_par_iban")) == {
        C: Decimal("12300.01"), D: Decimal("5000.00"),
        A: Decimal("250.50"), B: Decimal("49.50"),
    }


# --- 4. Les flags sont correctement positionnés -----------------------------

def test_seules_les_transactions_au_dessus_de_5000_sont_flaguees(base):
    flaguees = lire(base, "SELECT montant FROM transactions WHERE flag ORDER BY montant")
    assert flaguees == [(Decimal("5000.01"),), (Decimal("7200.00"),)]


def test_5000_pile_n_est_pas_flaguee(base):
    assert lire(base, "SELECT flag FROM transactions WHERE montant = 5000.00") == [(False,)]


# --- 5. Un fichier déjà traité n'est jamais retraité ------------------------

def test_relancer_la_pipeline_ne_cree_aucun_doublon(base):
    totaux_avant = lire(base, "SELECT iban, total FROM somme_envoyee_par_iban ORDER BY iban")

    bilan = executer_pipeline(REFERENCE, attente=0)      # 2e passage, même fichier

    assert bilan == {"traites": [], "ignores": ["transactions_reference.csv"]}
    assert lire(base, "SELECT COUNT(*) FROM transactions") == [(6,)]
    assert lire(base, "SELECT iban, total FROM somme_envoyee_par_iban ORDER BY iban") == totaux_avant