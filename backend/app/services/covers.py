"""Téléchargement local + redimensionnement des couvertures (§3).

Jamais de hotlink : l'image choisie est téléchargée côté backend, stockée
dans `covers/` sous `{book_id}/full.jpg` (600 px) et `{book_id}/thumb.jpg`
(200 px), servies ensuite par StaticFiles depuis `/covers/…`.

Sécurité :
- L'URL de départ doit pointer vers un hôte de la liste blanche
  (`ALLOWED_COVER_HOSTS`) : le front ne passe normalement que des URLs
  issues du lookup, c'est une défense en profondeur contre le SSRF.
- La taille téléchargée est bornée (`MAX_COVER_BYTES`).
- Le contenu est revalidé par Pillow : un octet-stream ne devient pas
  une couverture.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, UnidentifiedImageError

from app import config

logger = logging.getLogger(__name__)


class CoverError(Exception):
    """Erreur de téléchargement ou de traitement d'une couverture."""


def _check_host(url: str) -> None:
    host = (urlparse(url).hostname or "").lower()
    if not config._host_allowed(host):
        raise CoverError(f"hôte non autorisé : {host!r}")


def _validate_image(data: bytes) -> Image.Image:
    """Ouvre les octets avec Pillow et vérifie que c'est bien une image."""
    if len(data) > config.MAX_COVER_BYTES:
        raise CoverError("image trop volumineuse")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise CoverError("le fichier téléchargé n'est pas une image valide") from exc
    return img


def _resize_cover(img: Image.Image, width: int) -> Image.Image:
    """Redimensionne en gardant le ratio, largeur `width` fixe.

    Les couvertures sont des images 2/3 : on fixe la largeur et on laisse
    la hauteur suivre. LANCZOS pour une qualité de lecture correcte.
    """
    height = max(1, round(img.height * (width / max(img.width, 1))))
    return img.resize((width, height), Image.LANCZOS)


async def download_and_store(
    url: str, book_id: int, client: httpx.AsyncClient
) -> str:
    """Télécharge une couverture, la redimensionne en deux tailles et la
    stocke dans `covers/{book_id}/`.

    Retourne le chemin **relatif** au dossier covers du fichier full
    (ex. `12/full.jpg`), à persister dans `book.cover_path`.

    Sécurité SSRF : les redirections sont suivies (les couvertures Open
    Library vivent chez Internet Archive et 302 vers `archive.org`) mais
    **chaque hôte traversé** doit être dans la liste blanche — jamais de
    détour vers un domaine tiers.
    """
    resp = await _follow_allowed_redirects(url, client)
    if resp.status_code != 200:
        raise CoverError(f"HTTP {resp.status_code} au téléchargement")

    content_type = resp.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise CoverError(f"type de contenu inattendu : {content_type!r}")

    return store_image(resp.content, book_id)


async def _follow_allowed_redirects(url: str, client: httpx.AsyncClient) -> httpx.Response:
    """GET en suivant les redirections, hôte par hôte, jusqu'à 5 sauts.

    Vérifie la liste blanche sur l'URL de départ ET sur chaque destination.
    """
    current = url
    for _ in range(5):
        _check_host(current)
        try:
            resp = await client.get(current, follow_redirects=False, timeout=config.HTTP_TIMEOUT_SEC)
        except httpx.HTTPError as exc:
            raise CoverError(f"téléchargement échoué : {exc}") from exc

        if resp.status_code in (301, 302, 303, 307, 308):
            location = resp.headers.get("location")
            if not location:
                raise CoverError("redirection sans destination")
            current = str(httpx.URL(current).join(location))
            continue
        return resp

    raise CoverError("trop de redirections")


def store_image(data: bytes, book_id: int) -> str:
    """Valide des octets d'image et écrit les deux tailles sur disque.

    Utilisé par le téléchargement (URL) comme par l'upload manuel
    (multipart). Retourne le chemin relatif `{book_id}/full.jpg`.
    """
    img = _validate_image(data)

    covers_dir = config.COVERS_DIR
    book_dir = covers_dir / str(book_id)
    book_dir.mkdir(parents=True, exist_ok=True)

    full = _resize_cover(img, config.FULL_WIDTH)
    thumb = _resize_cover(img, config.THUMB_WIDTH)

    full_path = book_dir / "full.jpg"
    thumb_path = book_dir / "thumb.jpg"

    # JPEG : normalise le format quel que soit le format source (webp, png…).
    full.convert("RGB").save(full_path, "JPEG", quality=config.COVER_JPEG_QUALITY)
    thumb.convert("RGB").save(thumb_path, "JPEG", quality=config.COVER_JPEG_QUALITY)

    rel = f"{book_id}/full.jpg"
    logger.info("couverture stockée : %s", full_path)
    return rel
