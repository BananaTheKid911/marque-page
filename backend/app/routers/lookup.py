"""Router /api/v1/lookup — recherche et enrichissement métadonnées (§5).

Tous les appels externes partent d'ici (backend) : le front ne tape jamais
Open Library ni Google Books directement (règle métier).

Le client métadonnées est un **singleton** : son cache mémoire TTL (§3,
pour éviter les rate-limits) n'a de sens que s'il survit aux requêtes.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app import config
from app.schemas import CoverCandidate, LookupCandidate, LookupResult
from app.services.metadata import MetadataClient

router = APIRouter(prefix="/lookup", tags=["lookup"])

# Singleton — fermé dans le lifespan de main.py.
_metadata_client = MetadataClient()


def get_metadata_client() -> MetadataClient:
    return _metadata_client


async def close_metadata_client() -> None:
    await _metadata_client.aclose()


@router.get("", response_model=LookupResult | list[LookupCandidate])
async def lookup(
    isbn: str | None = Query(default=None, description="ISBN 10 ou 13"),
    q: str | None = Query(default=None, min_length=2, max_length=200,
                          description="Recherche par titre ou auteur"),
    client: MetadataClient = Depends(get_metadata_client),
) -> LookupResult | list[LookupCandidate]:
    """§3 — lookup par ISBN (métadonnées + couvertures candidates) ou
    recherche titre (top 10 candidats)."""
    if isbn:
        result = await client.lookup_by_isbn(isbn)
        if result is None:
            raise HTTPException(status_code=404, detail="ISBN introuvable")
        return result

    if q:
        return await client.search_title(q)

    raise HTTPException(
        status_code=422,
        detail="fournir `isbn` ou `q`",
    )


@router.get("/covers", response_model=list[CoverCandidate])
async def covers_variants(
    work: str | None = Query(default=None, description="Clé work Open Library (OL…W)"),
    isbn: str | None = Query(default=None, description="ISBN pour complément Google Books"),
    client: MetadataClient = Depends(get_metadata_client),
) -> list[CoverCandidate]:
    """§5 — variantes de couverture seules, pour un candidat choisi."""
    if not work and not isbn:
        raise HTTPException(status_code=422, detail="fournir `work` ou `isbn`")
    return await client.fetch_cover_variants(work, isbn)
