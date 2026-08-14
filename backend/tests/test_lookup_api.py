"""Tests du routeur /api/v1/lookup via TestClient (métadonnées mockées).

On vérifie le contrat HTTP (§5) : codes, forme de réponse, erreurs.
Le parsing détaillé est couvert dans test_metadata.py.
"""

import httpx

from app.services.metadata import MetadataClient
from tests.conftest import make_metadata_client, override_metadata_dep


def _edition_handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "openlibrary.org/isbn/9782070368228.json" in url:
        return httpx.Response(200, json={
            "key": "/books/OL8838059M",
            "title": "1984",
            "publishers": ["Gallimard"],
            "number_of_pages": 438,
            "isbn_13": ["9782070368228"],
            "covers": [967386],
            "works": [{"key": "/works/OL1168083W"}],
        })
    if "openlibrary.org/works/OL1168083W/editions.json" in url:
        return httpx.Response(200, json={
            "entries": [{"covers": [967386]}, {"covers": [42]}],
        })
    return httpx.Response(404)


class TestLookupRoute:
    def test_lookup_by_isbn(self, client):
        override_metadata_dep(make_metadata_client(_edition_handler))
        resp = client.get("/api/v1/lookup", params={"isbn": "9782070368228"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "1984"
        assert data["source"] == "openlibrary"
        assert len(data["covers"]) >= 1

    def test_lookup_by_query(self, client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={
                "docs": [{"key": "/works/OL1W", "title": "1984",
                          "author_name": ["George Orwell"]}],
            })

        override_metadata_dep(make_metadata_client(handler))
        resp = client.get("/api/v1/lookup", params={"q": "1984 orwell"})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert resp.json()[0]["title"] == "1984"

    def test_lookup_requires_isbn_or_q(self, client):
        override_metadata_dep(make_metadata_client(_edition_handler))
        assert client.get("/api/v1/lookup").status_code == 422

    def test_lookup_unknown_isbn_404(self, client):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        override_metadata_dep(make_metadata_client(handler))
        resp = client.get("/api/v1/lookup", params={"isbn": "0000000000000"})
        assert resp.status_code == 404

    def test_covers_variants(self, client):
        def handler(request: httpx.Request) -> httpx.Response:
            if "editions.json" in str(request.url):
                return httpx.Response(200, json={
                    "entries": [{"covers": [101]}, {"covers": [102]}],
                })
            return httpx.Response(404)

        override_metadata_dep(make_metadata_client(handler))
        resp = client.get("/api/v1/lookup/covers", params={"work": "OL1168083W"})
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_covers_requires_param(self, client):
        override_metadata_dep(make_metadata_client(_edition_handler))
        assert client.get("/api/v1/lookup/covers").status_code == 422


class TestMetadataClientLifecycle:
    def test_transport_injected(self):
        """Le transport mocké est bien utilisé par le client."""
        import asyncio

        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, json={"docs": []})

        client = MetadataClient(transport=httpx.MockTransport(handler))
        result = asyncio.run(client._get_json("https://openlibrary.org/search.json"))
        assert result == {"docs": []}
        assert len(calls) == 1
