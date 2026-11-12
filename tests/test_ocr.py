"""
Tests du NIVEAU 3, option 2 : extraction de transactions depuis des images (OCR).

Les images sont générées par generate_images.py : on connaît donc d'avance
ce que l'OCR doit lire (comme le fichier de référence pour les CSV).
⚠️ Nécessite Tesseract installé (sinon ces tests sont "sautés").
"""
import io
from decimal import Decimal

import pytest

from generate_images import AVIS, dessiner_avis
from src.pipeline.ocr import extraire_transaction, tesseract_disponible, transactions_depuis_image
from src.pipeline.pipeline import executer_pipeline
from src.pipeline.validation import valider_transactions
from tests.outils import base_vide, lire

besoin_tesseract = pytest.mark.skipif(not tesseract_disponible(), reason="Tesseract non installé")


def image_png(nom: str) -> bytes:
    tampon = io.BytesIO()
    dessiner_avis(AVIS[nom]).save(tampon, format="PNG")
    return tampon.getvalue()


def test_extraction_depuis_un_texte():
    """L'étape d'extraction seule, sans OCR : rapide et toujours exécutée."""
    texte = "AVIS DE VIREMENT\nDate : 2026-02-03 10:15:00\nIBAN Xmetteur : FR76 3000\nMontant : 12,50 EUR\n"
    assert extraire_transaction(texte) == {
        "datetime_transaction": "2026-02-03 10:15:00",
        "iban_origine": "FR76 3000",
        "montant": "12,50 EUR",
    }


@besoin_tesseract
def test_ocr_lit_correctement_le_recu_001():
    transactions = valider_transactions(transactions_depuis_image(image_png("recu_001.png")), "recu_001.png")
    assert transactions == [{
        "datetime_transaction": "2026-02-03 10:15:00",
        "iban_origine": "FR7630001007941234567890185",
        "pays_source": "FR",
        "banque_source": "BNP Paribas",
        "iban_destinataire": "DE89370400440532013000",
        "pays_destinataire": "DE",
        "montant": Decimal("6200.00"),
    }]


@besoin_tesseract
def test_les_images_rejoignent_le_meme_flux_que_les_csv():
    """Image -> OCR -> validation -> traitement -> base, avec le flag > 5000."""
    conn = base_vide()
    try:
        fichiers = [(nom, lambda nom=nom: image_png(nom)) for nom in AVIS]
        bilan = executer_pipeline(fichiers, attente=0)

        assert bilan["traites"] == ["recu_001.png", "recu_002.png"]
        assert lire(conn, "SELECT montant, flag FROM transactions ORDER BY montant") == [
            (Decimal("1250.50"), False),
            (Decimal("6200.00"), True),       # > 5000 : flaguée, comme pour un CSV
        ]
        assert dict(lire(conn, "SELECT banque, total FROM somme_envoyee_par_banque")) == {
            "BNP Paribas": Decimal("6200.00"), "CaixaBank": Decimal("1250.50"),
        }
    finally:
        conn.close()


def test_un_fichier_invalide_est_rejete_sans_bloquer_les_autres():
    conn = base_vide()
    try:
        mauvais = b"datetime_transaction,iban_origine,pays_source,banque_source,iban_destinataire,pays_destinataire,montant\n" \
                  b"2026-01-01 10:00:00,FR761234567890,FR,Banque X,DE987654321,DE,100.00\n"
        fichiers = [
            ("mauvais.csv", lambda: mauvais),
            ("transactions_reference.csv", lambda: open("tests/donnees/transactions_reference.csv", "rb").read()),
        ]
        bilan = executer_pipeline(fichiers, attente=0)

        assert bilan["rejetes"] == ["mauvais.csv"]
        assert bilan["traites"] == ["transactions_reference.csv"]
        assert lire(conn, "SELECT COUNT(*) FROM transactions") == [(6,)]   # seulement le bon fichier
    finally:
        conn.close()
