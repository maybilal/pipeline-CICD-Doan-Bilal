"""
TRAITEMENT des données : les calculs demandés par le sujet.

Toutes les fonctions ici sont PURES :
  1. elles ne modifient pas les données reçues ;
  2. elles n'utilisent que ce qu'on leur donne en paramètre (pas de fichier,
     pas de base de données, pas de variable globale qui change) ;
  3. mêmes données en entrée  =>  toujours le même résultat.
"""
from decimal import Decimal

SEUIL_FLAG = Decimal("5000")


def _somme_par(transactions: list[dict], colonne: str) -> dict:
    """
    Outil commun : additionne les montants en les regroupant selon une colonne.
    Ex. avec colonne="iban_origine" : {"FR76...185": 12300.00, "FR76...143": 5000.01}
    """
    sommes = {}  # dictionnaire NEUF : on ne touche pas aux données d'entrée
    for t in transactions:
        cle = t[colonne]
        sommes[cle] = sommes.get(cle, Decimal("0")) + t["montant"]
    return sommes


def somme_envoyee_par_iban(transactions: list[dict]) -> dict:
    """Combien chaque compte a-t-il ENVOYÉ au total ?"""
    return _somme_par(transactions, "iban_origine")


def somme_envoyee_par_banque(transactions: list[dict]) -> dict:
    """Combien chaque banque a-t-elle ENVOYÉ au total (tous ses comptes confondus) ?"""
    return _somme_par(transactions, "banque_source")


def somme_recue_par_iban(transactions: list[dict]) -> dict:
    """Combien chaque compte a-t-il REÇU au total ?"""
    return _somme_par(transactions, "iban_destinataire")


def ajouter_flags(transactions: list[dict], seuil: Decimal = SEUIL_FLAG) -> list[dict]:
    """
    Renvoie une NOUVELLE liste où chaque transaction a une colonne "flag" :
    True si le montant est STRICTEMENT supérieur au seuil (5000 pile => False).

    {**t, "flag": ...} crée une COPIE de la transaction avec la colonne en plus.
    L'original reste intact : c'est ce qui rend la fonction pure.
    """
    return [{**t, "flag": t["montant"] > seuil} for t in transactions]