"""
Niveau 2 — Envoie les fichiers générés (CSV, et images au Niveau 3) dans le stockage S3.

Étapes :
  1. attendre que le service S3 réponde ;
  2. créer le bucket (s'il n'existe pas) ;
  3. envoyer chaque fichier (CSV ou image) du dossier ;
  4. vérifier que chaque fichier est bien présent dans S3, avec la bonne taille.

Usage :
    python envoyer_s3.py            # envoie les CSV du dossier data/
    python envoyer_s3.py autre_dossier
"""
import sys
from pathlib import Path

from src.pipeline.pipeline import format_accepte
from src.pipeline.retry import EchecDefinitif
from src.pipeline.stockage_s3 import (
    BUCKET,
    attendre_s3,
    client_s3,
    creer_bucket,
    envoyer_fichier,
    lister_objets,
)


def main() -> None:
    dossier = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    fichiers = sorted(c for c in dossier.iterdir() if format_accepte(c.name)) if dossier.is_dir() else []
    if not fichiers:
        print(f"❌ Aucun fichier à envoyer dans '{dossier}/'. Lance d'abord : python generate_csv.py")
        sys.exit(1)

    s3 = client_s3()
    try:
        attendre_s3(s3)
    except EchecDefinitif as erreur:
        print(f"\n🛑 PIPELINE ARRÊTÉE : {erreur}")
        print("   Le service S3 est-il démarré ? (docker compose up -d s3)")
        sys.exit(1)
    creer_bucket(s3)

    # Envoi
    for chemin in fichiers:
        envoyer_fichier(s3, chemin)
        print(f"⬆️  {chemin.name} envoyé")

    # Vérification : chaque fichier doit être présent, avec la même taille qu'en local
    presents = lister_objets(s3)
    erreurs = [
        c.name for c in fichiers
        if presents.get(c.name) != c.stat().st_size
    ]
    if erreurs:
        print(f"❌ Fichiers absents ou incomplets dans S3 : {erreurs}")
        sys.exit(1)       # => la pipeline GitHub passe au ROUGE

    print(f"\n✅ Vérification OK : {len(fichiers)} fichier(s) présents dans le bucket '{BUCKET}'.")
    print(f"Contenu du bucket : {len(presents)} fichier(s)")
    for nom, taille in sorted(presents.items()):
        print(f"   {nom:<35} {taille:>6} octets")


if __name__ == "__main__":
    main()
