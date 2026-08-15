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


class TestStatusTransitions:
    """Transition `tbr` -> `reading` par le chemin MANUEL (décision produit
    15/08 — les chemins automatiques timer/KOReader ont leurs propres tests
    dans test_sessions.py et test_koreader.py), et cohérence des états
    dépendant du statut : quitter la Pile libère `tbr_rank`, cesser d'être
    `reading` libère `is_primary_reading`."""

    def _set_rank(self, db_engine, book_id, rank, note):
        from app.models import Book
        from sqlmodel import Session

        with Session(db_engine) as s:
            b = s.get(Book, book_id)
            b.tbr_rank = rank
            b.tbr_note = note
            s.commit()

    def _book_state(self, db_engine, book_id):
        from app.models import Book
        from sqlmodel import Session

        with Session(db_engine) as s:
            b = s.get(Book, book_id)
            return b.status, b.tbr_rank, b.tbr_note, b.is_primary_reading

    def test_manual_reading_via_status_endpoint(self, client):
        book = client.post("/api/v1/books", json={"title": "Dune"}).json()
        assert book["status"] == "tbr"

        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "reading"
        assert resp.json()["owned"] == 1

    def test_leaving_tbr_frees_rank_keeps_note(self, client, db_engine):
        """Quitter la Pile libère le rang (l'ordre n'a de sens que dans la
        liste) mais conserve la note (texte saisi, jamais effacé)."""
        book = client.post("/api/v1/books", json={"title": "Dune"}).json()
        self._set_rank(db_engine, book["id"], 2, "à lire avant la série TV")

        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        assert resp.status_code == 200
        status, rank, note, _ = self._book_state(db_engine, book["id"])
        assert status == "reading"
        assert rank is None
        assert note == "à lire avant la série TV"

    def test_patch_status_leaving_tbr_frees_rank(self, client, db_engine):
        """Le PATCH peut aussi changer le statut : les mêmes règles
        s'appliquent (books.py `_apply_status_rules` est partagé)."""
        book = client.post("/api/v1/books", json={"title": "Dune"}).json()
        self._set_rank(db_engine, book["id"], 5, None)

        resp = client.patch(f"/api/v1/books/{book['id']}", json={"status": "reading"})
        assert resp.status_code == 200
        _, rank, _, _ = self._book_state(db_engine, book["id"])
        assert rank is None

    def test_leaving_reading_frees_primary_flag(self, client, db_engine):
        """Cesser d'être `reading` libère `is_primary_reading` — l'index
        partiel unique exigerait de toute façon un seul flag actif."""
        from app.models import Book
        from sqlmodel import Session

        book = client.post("/api/v1/books", json={"title": "Dune"}).json()
        client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        with Session(db_engine) as s:
            b = s.get(Book, book["id"])
            b.is_primary_reading = 1
            s.commit()

        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "read"})
        assert resp.status_code == 200
        _, _, _, primary = self._book_state(db_engine, book["id"])
        assert primary == 0


class TestFormats:
    """Formats × possession PAR format (décision produit 15/08) : cumulables,
    `owned` par format — papier acheté + digital emprunté cohabitent."""

    def test_create_with_formats(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Dune",
            "formats": [
                {"type": "physique", "owned": True},
                {"type": "digital", "owned": False},  # emprunté, pas acheté
            ],
        })
        assert resp.status_code == 201, resp.text
        formats = resp.json()["formats"]
        assert formats == [
            {"type": "digital", "owned": False},
            {"type": "physique", "owned": True},
        ]  # trié par type

    def test_create_audio(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Audible", "formats": [{"type": "audio", "owned": True}],
        })
        assert resp.json()["formats"] == [{"type": "audio", "owned": True}]

    def test_patch_formats_replace(self, client):
        book = client.post("/api/v1/books", json={
            "title": "X", "formats": [{"type": "physique", "owned": True}],
        }).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={
            "formats": [{"type": "audio", "owned": False}],
        })
        assert resp.status_code == 200
        assert resp.json()["formats"] == [{"type": "audio", "owned": False}]

    def test_patch_empty_formats_clears(self, client):
        book = client.post("/api/v1/books", json={
            "title": "X", "formats": [{"type": "physique", "owned": True}],
        }).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"formats": []})
        assert resp.json()["formats"] == []

    def test_invalid_format_type_rejected(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "X", "formats": [{"type": "video", "owned": True}],
        })
        assert resp.status_code == 422

    def test_duplicate_format_rejected(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "X",
            "formats": [
                {"type": "physique", "owned": True},
                {"type": "physique", "owned": False},
            ],
        })
        assert resp.status_code == 422

    def test_format_missing_owned_rejected(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "X", "formats": [{"type": "physique"}],
        })
        assert resp.status_code == 422


class TestSeries:
    """Série (15/08) : nom unique upserté, numéro de tome décimal."""

    def test_create_with_series(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Dune", "series": "Les Dune", "series_index": 1,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["series_name"] == "Les Dune"
        assert data["series_id"] is not None
        assert data["series_index"] == 1

    def test_series_shared_by_name(self, client):
        b1 = client.post("/api/v1/books", json={
            "title": "Dune", "series": "Les Dune", "series_index": 1,
        }).json()
        b2 = client.post("/api/v1/books", json={
            "title": "Dune Messiah", "series": "Les Dune", "series_index": 2,
        }).json()
        assert b1["series_id"] == b2["series_id"]

        series = client.get("/api/v1/series").json()
        assert len(series) == 1
        assert series[0]["name"] == "Les Dune"
        assert series[0]["book_count"] == 2

    def test_hors_serie_decimal_index(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Hors-série", "series": "Les Dune", "series_index": 1.5,
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["series_index"] == 1.5

    def test_patch_series_empty_removes(self, client):
        book = client.post("/api/v1/books", json={
            "title": "Dune", "series": "Les Dune", "series_index": 1,
        }).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"series": ""})
        assert resp.status_code == 200
        assert resp.json()["series_id"] is None
        assert resp.json()["series_name"] is None
        assert resp.json()["series_index"] is None

    def test_patch_series_switch(self, client):
        book = client.post("/api/v1/books", json={
            "title": "Dune", "series": "Les Dune", "series_index": 1,
        }).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={
            "series": "Dune Universe", "series_index": 3,
        })
        assert resp.status_code == 200
        assert resp.json()["series_name"] == "Dune Universe"
        assert resp.json()["series_index"] == 3


class TestPriceAndPurchase:
    """Prix payé / date d'achat : un champ chacun, JAMAIS en wishlist
    (le prix y serait « constaté », pas « payé » — décision produit 15/08)."""

    def test_price_on_owned_book(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Dune", "price_paid": 12.99, "purchased_at": "2026-08-10",
        })
        assert resp.status_code == 201, resp.text
        assert resp.json()["price_paid"] == 12.99
        assert resp.json()["purchased_at"] == "2026-08-10"

    def test_wishlist_with_price_rejected_at_create(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Souhait", "status": "wishlist", "price_paid": 10,
        })
        assert resp.status_code == 422

    def test_patch_price_on_wishlist_rejected(self, client):
        book = client.post("/api/v1/books", json={"title": "S", "status": "wishlist"}).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"price_paid": 9.99})
        assert resp.status_code == 422

    def test_moving_owned_book_to_wishlist_with_price_rejected(self, client):
        book = client.post("/api/v1/books", json={"title": "Dune", "price_paid": 15}).json()
        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "wishlist"})
        assert resp.status_code == 422
        # Le livre est resté inchangé (pas de commit partiel).
        assert client.get(f"/api/v1/books/{book['id']}").json()["status"] == "tbr"

    def test_clear_price_before_wishlist_ok(self, client):
        book = client.post("/api/v1/books", json={"title": "Dune", "price_paid": 15}).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={
            "status": "wishlist", "price_paid": None, "purchased_at": None,
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "wishlist"
        assert resp.json()["price_paid"] is None


class TestPrimaryReading:
    """Livre « en cours » principal : flag exclusif parmi les `reading`
    (index partiel unique en base), désignation manuelle via PATCH."""

    def _make_reading(self, client, title):
        book = client.post("/api/v1/books", json={"title": title}).json()
        client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        return book

    def test_set_and_unset(self, client):
        book = self._make_reading(client, "A")
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"is_primary_reading": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_primary_reading"] is True

        resp = client.patch(f"/api/v1/books/{book['id']}", json={"is_primary_reading": False})
        assert resp.json()["is_primary_reading"] is False

    def test_exclusive_switch(self, client):
        """Désigner B déset automatiquement A (un seul vrai à la fois)."""
        a = self._make_reading(client, "A")
        b = self._make_reading(client, "B")
        client.patch(f"/api/v1/books/{a['id']}", json={"is_primary_reading": True})

        resp = client.patch(f"/api/v1/books/{b['id']}", json={"is_primary_reading": True})
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_primary_reading"] is True
        assert client.get(f"/api/v1/books/{a['id']}").json()["is_primary_reading"] is False

    def test_primary_requires_reading_status(self, client):
        book = client.post("/api/v1/books", json={"title": "TBR"}).json()  # tbr
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"is_primary_reading": True})
        assert resp.status_code == 422


class TestTbrRank:
    """Pile à lire = sélection ordonnée (15/08) : rang distinct du statut."""

    def test_rank_exposed_and_cleared(self, client):
        book = client.post("/api/v1/books", json={"title": "Dune"}).json()
        assert book["tbr_rank"] is None

        resp = client.patch(f"/api/v1/books/{book['id']}", json={"tbr_rank": 2})
        assert resp.status_code == 200
        assert resp.json()["tbr_rank"] == 2

        # Quitter la PAL libère le rang (règle dérivée du statut).
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"status": "reading"})
        assert resp.json()["tbr_rank"] is None

    def test_rank_forced_null_outside_tbr(self, client):
        book = client.post("/api/v1/books", json={"title": "X"}).json()
        client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"tbr_rank": 5})
        assert resp.json()["tbr_rank"] is None  # pas de rang hors de la PAL

    def test_sort_tbr_rank_nulls_last(self, client):
        r3 = client.post("/api/v1/books", json={"title": "C"}).json()
        r1 = client.post("/api/v1/books", json={"title": "A"}).json()
        r2 = client.post("/api/v1/books", json={"title": "B"}).json()
        unr = client.post("/api/v1/books", json={"title": "Sans rang"}).json()
        client.patch(f"/api/v1/books/{r1['id']}", json={"tbr_rank": 1})
        client.patch(f"/api/v1/books/{r2['id']}", json={"tbr_rank": 2})
        client.patch(f"/api/v1/books/{r3['id']}", json={"tbr_rank": 3})

        resp = client.get("/api/v1/books", params={"status": "tbr", "sort": "tbr_rank"})
        assert resp.status_code == 200
        titles = [b["title"] for b in resp.json()["items"]]
        assert titles == ["A", "B", "C", "Sans rang"]  # sans rang en dernier


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
