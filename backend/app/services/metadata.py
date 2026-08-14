"""Client métadonnées — Open Library (source principale) + Google Books (fallback).

Implantations du §3 : lookup par ISBN, recherche titre, agrégation des
variantes de couverture (édition Open Library par ISBN → work → toutes les
éditions du work → cover_id ; Google Books en complément).

Règles de robustesse :
- Open Library est la source de vérité. Google Books est un fallback
  *best-effort* : une erreur 429/500/réseau côté Google ne doit jamais
  faire échouer le lookup.
- Un cache mémoire court (TTL `METADATA_CACHE_TTL_SEC`) évite de cogner
  les rate-limits quand le même ISBN est consulté plusieurs fois.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app import config
from app.schemas import CoverCandidate, LookupCandidate, LookupResult

logger = logging.getLogger(__name__)

# Largeurs estimées (px) pour le tri des variantes par résolution décroissante.
# Open Library : -S ≈ 100, -M ≈ 250, -L ≈ 500. Google Books : tailles connues.
_OL_SIZE_WIDTH = {"S": 100, "M": 250, "L": 500}
_GB_SIZE_WIDTH = {"thumbnail": 128, "small": 200, "medium": 400, "large": 800}


def _clean_isbn(isbn: str) -> str:
    """Normalise un ISBN (tirets, espaces) sans valider la somme de contrôle."""
    return isbn.replace("-", "").replace(" ", "").strip()


def _https(url: str) -> str:
    """Force https — les imageLinks Google sont parfois servis en http."""
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return url


def _ol_cover_url(cover_id: int, size: str = "L") -> str:
    return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"


def _strip_work_prefix(work: str) -> str:
    """Normalise une clé work : `/works/OL1168083W` → `OL1168083W`."""
    return work.removeprefix("/works/").removeprefix("works/").strip()


def _extract_description(desc: Any) -> str | None:
    """Description OL : str ou dict `{"value": "…"}`."""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get("value")
    return None


class MetadataClient:
    """Client HTTP vers Open Library / Google Books, avec cache mémoire."""

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            timeout=config.HTTP_TIMEOUT_SEC,
            follow_redirects=True,
            transport=transport,
            headers={"User-Agent": config.HTTP_USER_AGENT},
        )
        self._cache: dict[str, tuple[float, Any]] = {}

    async def aclose(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Cache / GET
    # ------------------------------------------------------------------

    async def _get_json(self, url: str, params: dict | None = None) -> Any | None:
        """GET + cache mémoire TTL court. Retourne None sur 404, lève rien
        sur les autres erreurs : un fournisseur HS ne doit pas faire
        échouer le lookup (best-effort)."""
        cache_key = f"{url}?{params or ''}"
        now = time.monotonic()
        hit = self._cache.get(cache_key)
        if hit and hit[0] > now:
            return hit[1]

        try:
            resp = await self._client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("metadata GET échoué (%s) : %s", url, exc)
            return None

        if resp.status_code == 404:
            self._cache[cache_key] = (now + config.METADATA_CACHE_TTL_SEC, None)
            return None
        if resp.status_code != 200:
            logger.warning("metadata %s -> HTTP %s", url, resp.status_code)
            return None

        try:
            data = resp.json()
        except ValueError:
            return None

        self._cache[cache_key] = (now + config.METADATA_CACHE_TTL_SEC, data)
        return data

    # ------------------------------------------------------------------
    # Lookup par ISBN
    # ------------------------------------------------------------------

    async def lookup_by_isbn(self, isbn: str) -> LookupResult | None:
        """§3.1 — Open Library par ISBN, Google Books en fallback complet."""
        isbn = _clean_isbn(isbn)
        if not isbn:
            return None

        ol = await self._lookup_openlibrary_isbn(isbn)
        if ol:
            return ol

        gb = await self._lookup_google_isbn(isbn)
        if gb:
            return gb

        return None

    async def _lookup_openlibrary_isbn(self, isbn: str) -> LookupResult | None:
        edition = await self._get_json(f"https://openlibrary.org/isbn/{isbn}.json")
        if not edition:
            return None

        edition_key = edition.get("key", "").removeprefix("/books/")
        works = edition.get("works") or []
        work_key = works[0].get("key", "") if works else ""
        work = _strip_work_prefix(work_key)

        authors = await self._resolve_author_names(edition.get("authors") or [])

        isbn_10 = None
        isbn_13 = None
        for candidate in edition.get("isbn_10") or []:
            if candidate and len(_clean_isbn(candidate)) == 10:
                isbn_10 = candidate
                break
        for candidate in edition.get("isbn_13") or []:
            if candidate and len(_clean_isbn(candidate)) == 13:
                isbn_13 = candidate
                break

        language = None
        languages = edition.get("languages") or []
        if languages:
            lang_key = languages[0].get("key", "") if isinstance(languages[0], dict) else ""
            language = lang_key.removeprefix("/languages/") or None

        covers: list[CoverCandidate] = []
        for cover_id in edition.get("covers") or []:
            covers.append(CoverCandidate(
                url=_ol_cover_url(int(cover_id), "L"),
                width=_OL_SIZE_WIDTH["L"],
                source="openlibrary",
            ))

        # Variantes complémentaires : toutes les éditions du work (§3.1 —
        # garantit ≥ 2 couvertures à proposer au sélecteur).
        if work:
            covers.extend(await self._ol_work_covers(work))

        # Google Books par ISBN en complément (best-effort).
        gb_cover = await self._google_cover_by_isbn(isbn)
        if gb_cover:
            covers.append(gb_cover)

        covers = _dedup_and_sort(covers)

        return LookupResult(
            title=edition.get("title") or "Sans titre",
            subtitle=edition.get("subtitle"),
            authors=authors,
            isbn10=isbn_10,
            isbn13=isbn_13,
            publisher=(edition.get("publishers") or [None])[0],
            published_date=edition.get("publish_date"),
            page_count=edition.get("number_of_pages"),
            language=language,
            description=_extract_description(edition.get("description")),
            openlibrary_work=work or None,
            openlibrary_edition=edition_key or None,
            covers=covers,
            source="openlibrary",
        )

    async def _resolve_author_names(self, author_refs: list[dict]) -> list[str]:
        """Résout les noms d'auteurs depuis leurs clés OL, en parallèle.

        Limité à 5 auteurs (un livre en a rarement plus, et chaque appel
        coûte une requête). Un échec de résolution n'empêche pas le reste."""
        names: list[str] = []
        for ref in author_refs[:5]:
            name = ref.get("name")
            key = ref.get("key")
            if name:
                names.append(name)
                continue
            if not key:
                continue
            author = await self._get_json(f"https://openlibrary.org{key}.json")
            if author and author.get("name"):
                names.append(author["name"])
        return names

    async def _lookup_google_isbn(self, isbn: str) -> LookupResult | None:
        """Fallback complet quand Open Library ne trouve rien."""
        data = await self._get_json(
            "https://www.googleapis.com/books/v1/volumes",
            {"q": f"isbn:{isbn}", "maxResults": 1},
        )
        items = (data or {}).get("items") or []
        if not items:
            return None

        volume = items[0].get("volumeInfo", {})
        gb_id = items[0].get("id")

        isbn_10 = None
        isbn_13 = None
        for ident in volume.get("industryIdentifiers") or []:
            if ident.get("type") == "ISBN_10":
                isbn_10 = ident.get("identifier")
            elif ident.get("type") == "ISBN_13":
                isbn_13 = ident.get("identifier")

        covers: list[CoverCandidate] = []
        img_links = volume.get("imageLinks") or {}
        for size in ("large", "medium", "small", "thumbnail"):
            url = img_links.get(size)
            if not url:
                continue
            covers.append(CoverCandidate(
                url=_https(url),
                width=_GB_SIZE_WIDTH[size],
                source="google",
            ))
            break  # une seule variante par volume : la plus grande disponible

        return LookupResult(
            title=volume.get("title") or "Sans titre",
            subtitle=volume.get("subtitle"),
            authors=volume.get("authors") or [],
            isbn10=isbn_10,
            isbn13=isbn_13,
            publisher=(volume.get("publisher")),
            published_date=volume.get("publishedDate"),
            page_count=volume.get("pageCount"),
            language=volume.get("language"),
            description=volume.get("description"),
            openlibrary_work=None,
            openlibrary_edition=None,
            google_books_id=gb_id,
            covers=_dedup_and_sort(covers),
            source="google",
        )

    async def _google_cover_by_isbn(self, isbn: str) -> CoverCandidate | None:
        """Une variante Google Books pour compléter les couvertures OL."""
        data = await self._get_json(
            "https://www.googleapis.com/books/v1/volumes",
            {"q": f"isbn:{isbn}", "maxResults": 1},
        )
        items = (data or {}).get("items") or []
        if not items:
            return None
        img_links = items[0].get("volumeInfo", {}).get("imageLinks") or {}
        for size in ("large", "medium"):
            url = img_links.get(size)
            if url:
                return CoverCandidate(
                    url=_https(url), width=_GB_SIZE_WIDTH[size], source="google"
                )
        return None

    # ------------------------------------------------------------------
    # Recherche titre
    # ------------------------------------------------------------------

    async def search_title(self, query: str, limit: int = 10) -> list[LookupCandidate]:
        """§3.1 — top `limit` candidats Open Library ; fallback Google Books."""
        data = await self._get_json(
            "https://openlibrary.org/search.json",
            {
                "q": query,
                "limit": limit,
                "fields": "title,subtitle,author_name,key,cover_i,"
                          "first_publish_year,isbn,number_of_pages_median,"
                          "language,publisher",
            },
        )
        docs = (data or {}).get("docs") or []
        if docs:
            return [self._ol_search_doc_to_candidate(doc) for doc in docs]

        return await self._search_google_fallback(query, limit)

    @staticmethod
    def _ol_search_doc_to_candidate(doc: dict) -> LookupCandidate:
        cover_i = doc.get("cover_i")
        work = _strip_work_prefix(doc.get("key", ""))
        isbn_list = doc.get("isbn") or []
        isbn_10 = next((i for i in isbn_list if len(_clean_isbn(i)) == 10), None)
        isbn_13 = next((i for i in isbn_list if len(_clean_isbn(i)) == 13), None)
        languages = doc.get("language") or []

        return LookupCandidate(
            title=doc.get("title") or "Sans titre",
            subtitle=doc.get("subtitle"),
            authors=doc.get("author_name") or [],
            isbn10=isbn_10,
            isbn13=isbn_13,
            publisher=(doc.get("publisher") or [None])[0],
            published_date=str(doc["first_publish_year"]) if doc.get("first_publish_year") else None,
            page_count=doc.get("number_of_pages_median"),
            language=languages[0] if languages else None,
            openlibrary_work=work or None,
            cover_thumb=_ol_cover_url(int(cover_i), "S") if cover_i else None,
            source="openlibrary",
        )

    async def _search_google_fallback(self, query: str, limit: int) -> list[LookupCandidate]:
        data = await self._get_json(
            "https://www.googleapis.com/books/v1/volumes",
            {"q": query, "maxResults": min(limit, 20)},
        )
        items = (data or {}).get("items") or []
        candidates: list[LookupCandidate] = []
        for item in items[:limit]:
            volume = item.get("volumeInfo", {})
            gb_id = item.get("id")
            isbn_10 = isbn_13 = None
            for ident in volume.get("industryIdentifiers") or []:
                if ident.get("type") == "ISBN_10":
                    isbn_10 = ident.get("identifier")
                elif ident.get("type") == "ISBN_13":
                    isbn_13 = ident.get("identifier")

            img_links = volume.get("imageLinks") or {}
            thumb = None
            for size in ("small", "thumbnail"):
                if img_links.get(size):
                    thumb = _https(img_links[size])
                    break

            candidates.append(LookupCandidate(
                title=volume.get("title") or "Sans titre",
                subtitle=volume.get("subtitle"),
                authors=volume.get("authors") or [],
                isbn10=isbn_10,
                isbn13=isbn_13,
                publisher=volume.get("publisher"),
                published_date=volume.get("publishedDate"),
                page_count=volume.get("pageCount"),
                language=volume.get("language"),
                google_books_id=gb_id,
                cover_thumb=thumb,
                source="google",
            ))
        return candidates

    # ------------------------------------------------------------------
    # Variantes de couverture seules
    # ------------------------------------------------------------------

    async def fetch_cover_variants(
        self, work: str | None, isbn: str | None
    ) -> list[CoverCandidate]:
        """§3.1 — toutes les éditions du work Open Library + Google Books,
        dédupliquées et triées par résolution décroissante."""
        covers: list[CoverCandidate] = []
        if work:
            covers.extend(await self._ol_work_covers(work))
        if isbn:
            gb_cover = await self._google_cover_by_isbn(isbn)
            if gb_cover:
                covers.append(gb_cover)
        return _dedup_and_sort(covers)

    async def _ol_work_covers(self, work: str) -> list[CoverCandidate]:
        work = _strip_work_prefix(work)
        data = await self._get_json(
            f"https://openlibrary.org/works/{work}/editions.json", {"limit": 40}
        )
        entries = (data or {}).get("entries") or []
        seen: set[int] = set()
        covers: list[CoverCandidate] = []
        for entry in entries:
            for cover_id in entry.get("covers") or []:
                try:
                    cid = int(cover_id)
                except (TypeError, ValueError):
                    continue
                if cid in seen:
                    continue
                seen.add(cid)
                covers.append(CoverCandidate(
                    url=_ol_cover_url(cid, "L"),
                    width=_OL_SIZE_WIDTH["L"],
                    source="openlibrary",
                ))
        return covers


# ---------------------------------------------------------------------------
# Helpers de tri / dédup
# ---------------------------------------------------------------------------

def _dedup_and_sort(covers: list[CoverCandidate]) -> list[CoverCandidate]:
    """Déduplique par URL et trie par résolution décroissante."""
    seen: set[str] = set()
    unique: list[CoverCandidate] = []
    for cover in covers:
        if cover.url in seen:
            continue
        seen.add(cover.url)
        unique.append(cover)
    unique.sort(key=lambda c: c.width or 0, reverse=True)
    return unique
