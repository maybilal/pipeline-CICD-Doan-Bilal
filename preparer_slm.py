"""
Niveau 3 (option 3) — Prépare le SLM : attend que le service Ollama réponde,
puis télécharge le modèle s'il n'est pas déjà là (une seule fois, ~1 Go).

Usage :
    docker compose up -d slm
    python preparer_slm.py
"""
import sys

from src.pipeline.retry import EchecDefinitif
from src.pipeline.slm import preparer_slm

if __name__ == "__main__":
    try:
        preparer_slm()
    except EchecDefinitif as erreur:
        print(f"\n🛑 PIPELINE ARRÊTÉE : {erreur}")
        print("   Le service SLM est-il démarré ? (docker compose up -d slm)")
        sys.exit(1)
