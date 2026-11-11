"""
RETRY : réessayer automatiquement une opération qui échoue à cause d'un
problème TEMPORAIRE (base momentanément indisponible, coupure réseau...).

Ce module est générique : il servira aussi au Niveau 2 (récupération depuis S3).
"""
import time


class EchecDefinitif(Exception):
    """Levée quand l'opération échoue encore après le nombre maximal de tentatives."""


def avec_retry(fonction, description: str, erreurs_temporaires: tuple,
               max_tentatives: int = 3, attente_initiale: float = 1.0):
    """
    Exécute fonction(). En cas d'erreur TEMPORAIRE :
      - affiche l'erreur ;
      - attend (1 s, puis 2 s, puis 4 s... : on double à chaque fois) ;
      - réessaie, jusqu'à max_tentatives ;
      - au-delà, abandonne en levant EchecDefinitif (ce qui arrête la pipeline).

    Les autres erreurs (ex. une donnée invalide) ne sont PAS réessayées :
    réessayer ne les corrigerait pas.
    """
    attente = attente_initiale
    for tentative in range(1, max_tentatives + 1):
        try:
            return fonction()
        except erreurs_temporaires as erreur:
            message = str(erreur).strip().splitlines()[0] if str(erreur).strip() else repr(erreur)
            print(f"⚠️  Échec de {description} (tentative {tentative}/{max_tentatives}) : {message}")
            if tentative == max_tentatives:
                print(f"❌ Abandon de {description} après {max_tentatives} tentatives.")
                raise EchecDefinitif(
                    f"{description} : échec après {max_tentatives} tentatives ({message})"
                ) from erreur
            print(f"   ⏳ Nouvelle tentative dans {attente:g} s...")
            time.sleep(attente)
            attente *= 2