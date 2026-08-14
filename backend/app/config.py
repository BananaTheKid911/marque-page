"""Configuration de Marque-page — chemins et constantes.

Les valeurs sensibles (APP_PASSWORD) ne sont pas lues ici : elles arriveront
avec l'auth en Phase 2+. Cette phase lit uniquement ce qui concerne les
couvertures et les appels externes.
"""

import os
from pathlib import Path

# Dossier des couvertures. Défaut : volume Docker /app/covers (compose).
# Surchargeable via MARQUEPAGE_COVERS pour le dev hors conteneur et les tests.
COVERS_DIR = Path(os.environ.get("MARQUEPAGE_COVERS", "/app/covers"))

# Tailles de redimensionnement (SPEC.md §3 : thumb 200 px, full 600 px).
# Largeur fixe, hauteur conservée (ratio de la couverture d'origine).
THUMB_WIDTH = 200
FULL_WIDTH = 600

# JPEG qualité pour la normalisation des couvertures.
COVER_JPEG_QUALITY = 85

# Timeout des appels HTTP sortants (Open Library, Google Books, covers).
HTTP_TIMEOUT_SEC = 15.0

# User-Agent identifiant l'app (certains fournisseurs le demandent).
HTTP_USER_AGENT = "marquepage/0.1 (self-hosted reading tracker; +tailnet)"

# Taille maximale d'une image téléchargée (octets) — 12 Mo, couvertures raisonnables.
MAX_COVER_BYTES = 12 * 1024 * 1024

# Domaines autorisés pour le téléchargement d'une couverture par URL.
# Le front ne passe normalement que des URLs issues du lookup ; cette liste
# blanche est une défense en profondeur contre une URL arbitraire (SSRF léger).
# `archive.org` (+ sous-domaines) est l'hébergeur réel des images Open Library :
# les couvertures OL 302 vers https://archive.org/download/…
ALLOWED_COVER_HOSTS = {
    "covers.openlibrary.org",
    "archive.org",
    "books.google.com",
    "books.googleusercontent.com",
    "upload.wikimedia.org",
}


def _host_allowed(host: str) -> bool:
    """Un hôte est autorisé s'il est exact dans la liste blanche ou un
    sous-domaine d'un domaine listé (ex. `ia801009.us.archive.org`)."""
    host = host.lower().rstrip(".")
    if host in ALLOWED_COVER_HOSTS:
        return True
    return any(host.endswith("." + allowed) for allowed in ALLOWED_COVER_HOSTS)

# Durée de vie du cache mémoire des réponses métadonnées (secondes).
METADATA_CACHE_TTL_SEC = 300
