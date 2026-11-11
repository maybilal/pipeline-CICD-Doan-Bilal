"""
La pipeline complète : pour chaque fichier, charger -> traiter -> insérer.

- Chaque fichier est traité SÉPARÉMENT : un fichier déjà traité est ignoré.
- L'insertion est protégée par un retry (pannes temporaires de la base).

main.py l'utilise pour le vrai traitement, et les tests l'utilisent aussi.
"""
import hashlib
from pathlib import Path

import psycopg2

from src.pipeline.base_de_donnees import (
    connexion,
    creer_tables,
    fichier_deja_traite,
    inserer_resultats,
)
from src.pipeline.chargement import charger_csv
from src.pipeline.retry import avec_retry
from src.pipeline.traitement import (
    ajouter_flags,
    somme_envoyee_par_banque,
    somme_envoyee_par_iban,
    somme_recue_par_iban,
)


def empreinte_fichier(chemin: Path) -> str:
    """
    Calcule l'empreinte SHA-256 du CONTENU du fichier : une suite de 64 caractères
    qui change complètement si un seul caractère du fichier change.
    """
    return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()


def lister_fichiers(source: str | Path) -> list[Path]:
    source = Path(source)
    return [source] if source.is_file() else sorted(source.glob("*.csv"))


def traiter_fichier(chemin: Path, connecter=connexion,
                    max_tentatives: int = 3, attente: float = 1.0) -> bool:
    """
    Traite UN fichier. Renvoie True s'il a été inséré, False s'il était déjà traité.
    """
    # 1. CHARGEMENT et 2. TRAITEMENT (pas de base de données ici)
    transactions = charger_csv(chemin)
    empreinte = empreinte_fichier(chemin)
    resultats = (
        ajouter_flags(transactions),
        somme_envoyee_par_iban(transactions),
        somme_recue_par_iban(transactions),
        somme_envoyee_par_banque(transactions),
    )

    # 3. BASE DE DONNÉES : une "tentative" complète, que le retry peut rejouer.
    def tentative() -> bool:
        conn = connecter()            # nouvelle connexion à chaque tentative
        try:
            creer_tables(conn)
            if fichier_deja_traite(conn, empreinte):
                return False          # déjà fait : on ne touche à rien
            inserer_resultats(conn, chemin.name, empreinte, *resultats)
            return True
        finally:
            conn.close()

    return avec_retry(
        tentative,
        description=f"l'insertion de {chemin.name}",
        erreurs_temporaires=(psycopg2.OperationalError,),   # erreurs de connexion
        max_tentatives=max_tentatives,
        attente_initiale=attente,
    )


def executer_pipeline(source: str | Path, connecter=connexion,
                      max_tentatives: int = 3, attente: float = 1.0) -> dict:
    """Traite un fichier ou tous les CSV d'un dossier. Renvoie le bilan."""
    bilan = {"traites": [], "ignores": []}
    for chemin in lister_fichiers(source):
        if traiter_fichier(chemin, connecter, max_tentatives, attente):
            print(f"✅ {chemin.name} : traité et inséré")
            bilan["traites"].append(chemin.name)
        else:
            print(f"⏭️  {chemin.name} : déjà traité, ignoré")
            bilan["ignores"].append(chemin.name)
    return bilan