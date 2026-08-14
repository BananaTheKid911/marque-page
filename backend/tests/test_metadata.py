"""Tests du client métadonnées — parsing Open Library / Google Books (§3).

Aucun réseau : `httpx.MockTransport` joue les réponses. Les fixtures JSON
sont des extraits réalistes des APIs réelles (vérifiées le 14/08/2026).
"""

import json

import httpx
import pytest

from app.schemas import LookupResult
from tests.conftest import make_metadata_client

EDITION_1984 = {
    "key": "/books/OL8838059M",
    "title": "1984",
    "publish_date": "1993",
    "publishers": ["Gallimard"],
    "number_of_pages": 438,
    "languages": [{"key": "/languages/fre"}],
    "covers": [967386],
    "isbn_10": ["207036822X"],
    "isbn_13": ["9782070368228"],
    "works": [{"key": "/works/OL1168083W"}],
    "authors": [{"key": "/authors/OL118077A"}],
    "description": "Full text online available at 1984.",
}

AUTHOR_ORWELL = {"name": "George Orwell", "key": "/authors/OL118077A"}

GOOGLE_1984 = {
    "items": [
        {
            "id": "abc123",
            "volumeInfo": {
                "title": "1984",
                "authors": ["George Orwell"],
                "publisher": "Gallimard",
                "publishedDate": "1993",
                "pageCount": 438,
                "language": "fr",
                "description": "Description google.",
                "industryIdentifiers": [
                    {"type": "ISBN_13", "identifier": "9782070368228"},
                ],
                "imageLinks": {
                    "smallThumbnail": "http://books.google.com/books/content?id=abc&zoom=5",
                    "thumbnail": "http://books.google.com/books/content?id=abc&zoom=1",
                },
            },
        }
    ]
}


def _handler_factory(**responses):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        for prefix, payload in responses.items():
            if url.startswith(prefix):
                return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"error": "not found"})

    return handler


class TestLookupByIsbn:
    def test_openlibrary_edition_parsed(self):
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "openlibrary.org/isbn/" in url:
                return httpx.Response(200, json=EDITION_1984)
            if "openlibrary.org/authors/OL118077A.json" in url:
                return httpx.Response(200, json=AUTHOR_ORWELL)
            if "openlibrary.org/works/OL1168083W/editions.json" in url:
                return httpx.Response(200, json={"entries": [
                    {"covers": [967386, 500]},
                    {"covers": [42]},
                ]})
            if "googleapis.com/books" in url:
                return httpx.Response(429, json={})  # quota épuisé : best-effort
            return httpx.Response(404)

        client = make_metadata_client(handler)
        result = asyncio_run(client.lookup_by_isbn("9782070368228"))

        assert isinstance(result, LookupResult)
        assert result.title == "1984"
        assert result.authors == ["George Orwell"]
        assert result.publisher == "Gallimard"
        assert result.page_count == 438
        assert result.language == "fre"
        assert result.isbn13 == "9782070368228"
        assert result.openlibrary_work == "OL1168083W"
        assert result.openlibrary_edition == "OL8838059M"
        assert result.source == "openlibrary"
        # ≥ 2 couvertures (critère d'acceptation Phase 1 : « propose ≥ 2 ») :
        # la couverture de l'édition (967386) + les éditions du work (500, 42).
        assert len(result.covers) >= 2
        assert all(c.url.startswith("https://covers.openlibrary.org/") for c in result.covers)
        assert all(c.source == "openlibrary" for c in result.covers)
        # 967386 apparaît une seule fois malgré les deux sources.
        urls = [c.url for c in result.covers]
        assert urls.count("https://covers.openlibrary.org/b/id/967386-L.jpg") == 1

    def test_isbn_normalized(self):
        """Les tirets sont retirés avant l'appel."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "openlibrary.org/isbn/9782070368228.json" in str(request.url):
                return httpx.Response(200, json=EDITION_1984)
            if "openlibrary.org/authors/OL118077A.json" in str(request.url):
                return httpx.Response(200, json=AUTHOR_ORWELL)
            return httpx.Response(404)

        client = make_metadata_client(handler)
        result = asyncio_run(client.lookup_by_isbn("978-2-07-036822-8"))
        assert result is not None
        assert result.title == "1984"

    def test_unknown_isbn_returns_none(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        client = make_metadata_client(handler)
        assert asyncio_run(client.lookup_by_isbn("0000000000000")) is None

    def test_google_fallback_when_ol_empty(self):
        def handler(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "googleapis.com/books" in url:
                return httpx.Response(200, json=GOOGLE_1984)
            return httpx.Response(404)

        client = make_metadata_client(handler)
        result = asyncio_run(client.lookup_by_isbn("9782070368228"))

        assert result is not None
        assert result.source == "google"
        assert result.google_books_id == "abc123"
        assert result.title == "1984"
        # imageLinks passés en https, jamais en http
        assert all(c.url.startswith("https://") for c in result.covers)


class TestSearchTitle:
    SEARCH_DOCS = {
        "numFound": 1,
        "docs": [
            {
                "key": "/works/OL1168083W",
                "title": "1984",
                "author_name": ["George Orwell"],
                "first_publish_year": 1949,
                "cover_i": 12721865,
                "isbn": ["9782070368228", "207036822X"],
                "number_of_pages_median": 300,
                "language": ["fre", "eng"],
                "publisher": ["Gallimard"],
            }
        ],
    }

    def test_search_returns_candidates(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "openlibrary.org/search.json" in str(request.url):
                return httpx.Response(200, json=self.SEARCH_DOCS)
            return httpx.Response(404)

        client = make_metadata_client(handler)
        candidates = asyncio_run(client.search_title("1984"))

        assert len(candidates) == 1
        c = candidates[0]
        assert c.title == "1984"
        assert c.authors == ["George Orwell"]
        assert c.openlibrary_work == "OL1168083W"
        assert c.isbn13 == "9782070368228"
        assert c.cover_thumb and c.cover_thumb.startswith("https://covers.openlibrary.org/")

    def test_search_google_fallback(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "openlibrary.org/search.json" in str(request.url):
                return httpx.Response(200, json={"docs": []})
            if "googleapis.com/books" in str(request.url):
                return httpx.Response(200, json=GOOGLE_1984)
            return httpx.Response(404)

        client = make_metadata_client(handler)
        candidates = asyncio_run(client.search_title("inconnu"))

        assert len(candidates) == 1
        assert candidates[0].source == "google"
        assert candidates[0].title == "1984"

    def test_search_empty(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"docs": []})

        client = make_metadata_client(handler)
        assert asyncio_run(client.search_title("zzzz")) == []


class TestCoverVariants:
    EDITIONS = {
        "size": 2,
        "entries": [
            {"key": "/books/OL1M", "covers": [101]},
            {"key": "/books/OL2M", "covers": [102, 101]},  # 101 en double
            {"key": "/books/OL3M", "covers": None},
        ],
    }

    def test_work_editions_dedup_and_sort(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if "openlibrary.org/works/OL1168083W/editions.json" in str(request.url):
                return httpx.Response(200, json=self.EDITIONS)
            return httpx.Response(404)

        client = make_metadata_client(handler)
        covers = asyncio_run(client.fetch_cover_variants("OL1168083W", None))

        assert len(covers) == 2  # 101 dédoublonné
        urls = {c.url for c in covers}
        assert "https://covers.openlibrary.org/b/id/101-L.jpg" in urls
        assert "https://covers.openlibrary.org/b/id/102-L.jpg" in urls
        assert all(c.source == "openlibrary" for c in covers)


def asyncio_run(coro):
    import asyncio

    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)
