"""Tests du CRUD /books et de la gestion des couvertures (§5).

La DB est un SQLite frais par test (fixture `client`), les clients HTTP
sortants sont mockés. On vérifie les règles métier : wishlist→owned=0,
current_percent recalculé, upsert auteurs, download local de couverture.
"""

import io

import httpx
from PIL import Image

from tests.conftest import override_http_deps


def _jpeg_bytes(width=300, height=450) -> bytes:
    """Génère une vraie image JPEG en mémoire (2/3, comme une couverture)."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (120, 60, 30)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


class TestCreateBook:
    def test_create_manual(self, client):
        resp = client.post("/api/v1/books", json={"title": "Le Meilleur des mondes"})
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["title"] == "Le Meilleur des mondes"
        assert data["status"] == "tbr"
        assert data["owned"] == 1
        assert data["current_page"] == 0
        assert data["current_percent"] == 0
        assert data["authors"] == []

    def test_wishlist_forces_owned_0(self, client):
        resp = client.post("/api/v1/books", json={"title": "Souhait", "status": "wishlist"})
        assert resp.status_code == 201
        assert resp.json()["owned"] == 0
        assert resp.json()["status"] == "wishlist"

    def test_status_invalid_rejected(self, client):
        resp = client.post("/api/v1/books", json={"title": "X", "status": "périmé"})
        assert resp.status_code == 422

    def test_rating_bounds(self, client):
        assert client.post("/api/v1/books", json={"title": "X", "rating": 5.5}).status_code == 422
        assert client.post("/api/v1/books", json={"title": "X", "rating": 0.4}).status_code == 422

    def test_create_with_authors(self, client):
        resp = client.post(
            "/api/v1/books",
            json={"title": "Dune", "authors": ["Frank Herbert"]},
        )
        assert resp.status_code == 201
        assert resp.json()["authors"] == ["Frank Herbert"]

    def test_current_percent_recomputed(self, client):
        resp = client.post(
            "/api/v1/books",
            json={"title": "Z", "page_count": 400, "current_page": 100},
        )
        assert resp.status_code == 201
        assert resp.json()["current_percent"] == 0.25

    def test_create_with_cover_downloads_locally(self, client, tmp_path, monkeypatch):
        """La sélection d'une variante télécharge l'image et la sert en local."""
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        img = _jpeg_bytes()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                content=img,
                headers={"content-type": "image/jpeg"},
            )

        override_http_deps(handler)
        resp = client.post(
            "/api/v1/books",
            json={
                "title": "1984",
                "cover_url": "https://covers.openlibrary.org/b/id/967386-L.jpg",
                "cover_source": "openlibrary",
            },
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["cover_path"] == "1/full.jpg"
        assert data["cover_url"] == "/covers/1/full.jpg"
        assert data["cover_thumb_url"] == "/covers/1/thumb.jpg"

        # Les deux fichiers existent ; le full fait 600 px, le thumb 200 px.
        full = covers_dir / "1" / "full.jpg"
        thumb = covers_dir / "1" / "thumb.jpg"
        assert full.exists() and thumb.exists()
        with Image.open(thumb) as t:
            assert t.width == 200
        with Image.open(full) as f:
            assert f.width == 600

    def test_cover_host_whitelist(self, client, tmp_path, monkeypatch):
        """Un hôte hors liste blanche est refusé avant tout téléchargement,
        et le livre n'est pas créé (transaction atomique)."""
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        resp = client.post(
            "/api/v1/books",
            json={
                "title": "X",
                "cover_url": "https://evil.example.com/cover.jpg",
            },
        )
        assert resp.status_code == 422
        assert "couverture" in resp.json()["detail"]
        # Rien n'a été persisté : la liste est vide.
        assert client.get("/api/v1/books").json()["total"] == 0

    def test_cover_follows_redirects_to_allowed_host(self, client, tmp_path, monkeypatch):
        """Les couvertures OL 302 vers archive.org : la redirection vers un
        hôte autorisé est suivie (et chaque hôte est vérifié)."""
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        img = _jpeg_bytes()
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            if "covers.openlibrary.org" in str(request.url):
                return httpx.Response(
                    302,
                    headers={"location": "https://archive.org/download/olcovers96/olcovers96-L.zip/967386-L.jpg"},
                )
            return httpx.Response(200, content=img, headers={"content-type": "image/jpeg"})

        override_http_deps(handler)
        resp = client.post(
            "/api/v1/books",
            json={
                "title": "1984",
                "cover_url": "https://covers.openlibrary.org/b/id/967386-L.jpg",
            },
        )
        assert resp.status_code == 201, resp.text
        assert (covers_dir / "1" / "thumb.jpg").exists()
        assert len(seen) == 2  # départ + redirection

    def test_cover_redirect_to_forbidden_host_rejected(self, client, tmp_path, monkeypatch):
        """Une redirection vers un hôte hors liste blanche est refusée."""
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        def handler(request: httpx.Request) -> httpx.Response:
            if "covers.openlibrary.org" in str(request.url):
                return httpx.Response(
                    302, headers={"location": "https://evil.example.com/cover.jpg"}
                )
            return httpx.Response(200, content=b"x")

        override_http_deps(handler)
        resp = client.post(
            "/api/v1/books",
            json={"title": "X", "cover_url": "https://covers.openlibrary.org/b/id/1-L.jpg"},
        )
        assert resp.status_code == 422
        assert client.get("/api/v1/books").json()["total"] == 0


class TestReadBook:
    def test_get_created_book(self, client):
        created = client.post("/api/v1/books", json={"title": "La Peste"}).json()
        resp = client.get(f"/api/v1/books/{created['id']}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "La Peste"

    def test_get_missing(self, client):
        assert client.get("/api/v1/books/9999").status_code == 404


class TestListBooks:
    def _seed(self, client):
        client.post("/api/v1/books", json={"title": "Alpha", "status": "read"})
        client.post("/api/v1/books", json={"title": "Bêta", "status": "tbr"})
        client.post("/api/v1/books", json={"title": "Gamma", "status": "tbr"})

    def test_list_all(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["page"] == 1

    def test_filter_status(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"status": "tbr"})
        assert resp.json()["total"] == 2

    def test_search_q(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"q": "alph"})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "Alpha"

    def test_pagination(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"page": 2, "page_size": 2})
        assert resp.json()["total"] == 3
        assert len(resp.json()["items"]) == 1


class TestUpdateBook:
    def test_patch_status_and_percent(self, client):
        book = client.post(
            "/api/v1/books",
            json={"title": "Z", "page_count": 200},
        ).json()
        resp = client.patch(
            f"/api/v1/books/{book['id']}",
            json={"status": "reading", "current_page": 50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "reading"
        assert data["current_percent"] == 0.25

    def test_patch_replaces_authors(self, client):
        book = client.post(
            "/api/v1/books",
            json={"title": "Dune", "authors": ["Frank Herbert"]},
        ).json()
        resp = client.patch(
            f"/api/v1/books/{book['id']}",
            json={"authors": ["Frank Herbert", "Brian Herbert"]},
        )
        assert resp.json()["authors"] == ["Brian Herbert", "Frank Herbert"]

    def test_patch_missing(self, client):
        assert client.patch("/api/v1/books/9999", json={"title": "X"}).status_code == 404


class TestDeleteBook:
    def test_delete(self, client):
        book = client.post("/api/v1/books", json={"title": "À jeter"}).json()
        resp = client.delete(f"/api/v1/books/{book['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/books/{book['id']}").status_code == 404

    def test_delete_missing(self, client):
        assert client.delete("/api/v1/books/9999").status_code == 404


class TestSetCover:
    def test_upload_manual(self, client, tmp_path, monkeypatch):
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        book = client.post("/api/v1/books", json={"title": "Manuel"}).json()
        resp = client.post(
            f"/api/v1/books/{book['id']}/cover",
            files={"file": ("couverture.jpg", _jpeg_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["cover_source"] == "upload"
        assert (covers_dir / str(book["id"]) / "thumb.jpg").exists()

    def test_select_variant_json(self, client, tmp_path, monkeypatch):
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        img = _jpeg_bytes()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=img, headers={"content-type": "image/jpeg"})

        override_http_deps(handler)

        book = client.post("/api/v1/books", json={"title": "Variante"}).json()
        resp = client.post(
            f"/api/v1/books/{book['id']}/cover",
            json={"url": "https://covers.openlibrary.org/b/id/42-L.jpg", "source": "openlibrary"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["cover_source"] == "openlibrary"
        assert resp.json()["cover_url"].startswith("/covers/")

    def test_upload_invalid_content(self, client):
        book = client.post("/api/v1/books", json={"title": "Mauvais"}).json()
        resp = client.post(
            f"/api/v1/books/{book['id']}/cover",
            files={"file": ("x.jpg", b"pas une image", "image/jpeg")},
        )
        assert resp.status_code == 422
        assert "couverture" in resp.json()["detail"]

    def test_cover_on_missing_book(self, client):
        resp = client.post("/api/v1/books/9999/cover", json={"url": "https://covers.openlibrary.org/b/id/1-L.jpg"})
        assert resp.status_code == 404

    def test_unsupported_content_type(self, client):
        book = client.post("/api/v1/books", json={"title": "Texte"}).json()
        resp = client.post(
            f"/api/v1/books/{book['id']}/cover",
            content=b"x" * 10,
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 415
