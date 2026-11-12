"""
Tests UNITAIRES de la validation (fonctions pures, sans base ni S3).
"""
from decimal import Decimal

import pytest

from src.pipeline.validation import (
    DonneeInvalide,
    iban_valide,
    normaliser_montant,
    valider_transaction,
)

TRANSACTION_OK = {
    "datetime_transaction": "2026-02-03 10:15",
    "iban_origine": "fr76 3000 1007 9412 3456 7890 185",
    "banque_source": "BNP Paribas",
    "iban_destinataire": "DE89 3704 0044 0532 0130 00",
    "montant": "6 200,00 EUR",
}


def test_une_transaction_correcte_est_nettoyee():
    assert valider_transaction(TRANSACTION_OK) == {
        "datetime_transaction": "2026-02-03 10:15:00",
        "iban_origine": "FR7630001007941234567890185",
        "pays_source": "FR",                     # déduit de l'IBAN
        "banque_source": "BNP Paribas",
        "iban_destinataire": "DE89370400440532013000",
        "pays_destinataire": "DE",               # déduit de l'IBAN
        "montant": Decimal("6200.00"),
    }


@pytest.mark.parametrize("texte, attendu", [
    ("6200", "6200.00"),
    ("6 200,00 €", "6200.00"),
    ("1,250.50 EUR", "1250.50"),
    ("1.250,50", "1250.50"),
])
def test_les_formats_de_montant_sont_compris(texte, attendu):
    assert normaliser_montant(texte) == Decimal(attendu)


def test_cle_de_controle_iban():
    assert iban_valide("FR7630001007941234567890185")
    assert not iban_valide("FR7630001007941234567890186")   # un seul chiffre change
    assert not iban_valide("FR761234567890")                 # l'exemple (fictif) du sujet


@pytest.mark.parametrize("champ, valeur", [
    ("iban_origine", "FR7630001007941234567890186"),   # mauvaise clé (ex. erreur d'OCR)
    ("iban_destinataire", ""),                          # information manquante
    ("montant", "-50"),                                 # montant négatif
    ("montant", "beaucoup"),                            # montant illisible
    ("datetime_transaction", "hier soir"),              # date illisible
])
def test_les_donnees_invalides_sont_rejetees(champ, valeur):
    with pytest.raises(DonneeInvalide):
        valider_transaction({**TRANSACTION_OK, champ: valeur})


def test_la_validation_ne_modifie_pas_l_entree():
    copie = dict(TRANSACTION_OK)
    valider_transaction(TRANSACTION_OK)
    assert TRANSACTION_OK == copie
