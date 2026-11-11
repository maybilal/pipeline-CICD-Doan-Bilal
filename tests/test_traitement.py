"""
Tests UNITAIRES des calculs : pas de base de données, juste les fonctions pures.
On leur donne le fichier de référence et on compare avec le "corrigé".
"""
from copy import deepcopy
from decimal import Decimal

from src.pipeline.chargement import charger_csv
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)

REFERENCE = "tests/donnees/transactions_reference.csv"

# Les 4 comptes du fichier de référence
A = "FR7630001007941234567890185"
B = "FR7630004000031234567890143"
C = "DE89370400440532013000"
D = "DE44500105175407324931"


def test_somme_envoyee_par_iban():
    assert somme_envoyee_par_iban(charger_csv(REFERENCE)) == {
        A: Decimal("12300.00"), B: Decimal("5000.01"),
        C: Decimal("250.50"), D: Decimal("49.50"),
    }


def test_somme_envoyee_par_banque():
    assert somme_envoyee_par_banque(charger_csv(REFERENCE)) == {
        "BNP Paribas": Decimal("17300.01"),
        "Commerzbank": Decimal("250.50"),
        "Deutsche Bank": Decimal("49.50"),
    }


def test_somme_recue_par_iban():
    assert somme_recue_par_iban(charger_csv(REFERENCE)) == {
        C: Decimal("12300.01"), D: Decimal("5000.00"),
        A: Decimal("250.50"), B: Decimal("49.50"),
    }


def test_flags_strictement_superieur_a_5000():
    resultat = ajouter_flags(charger_csv(REFERENCE))
    flags = {t["montant"]: t["flag"] for t in resultat}
    assert flags[Decimal("5000.01")] is True
    assert flags[Decimal("7200.00")] is True
    assert flags[Decimal("5000.00")] is False   # 5000 pile : PAS flaguée
    assert sum(t["flag"] for t in resultat) == 2


def test_les_fonctions_sont_pures():
    transactions = charger_csv(REFERENCE)
    copie_avant = deepcopy(transactions)

    resultat_1 = ajouter_flags(transactions)
    resultat_2 = ajouter_flags(transactions)
    somme_envoyee_par_iban(transactions)

    assert transactions == copie_avant      # l'entrée n'a pas été modifiée
    assert resultat_1 == resultat_2         # même entrée => même résultat