"""Tests Phase 2 — taxonomie : tags/genres/auteurs, filtres, statut (§5).

Critère d'acceptation Phase 2 : « Filtrer par auteur/genre/tag fonctionne ;
déplacer un livre entre statuts marche. »
"""


class TestLabelsOnBook:
    def test_create_with_tags_and_genres(self, client):
        resp = client.post("/api/v1/books", json={
            "title": "Dune",
            "authors": ["Frank Herbert"],
            "tags": ["space-opera", "classique"],
            "genres": ["Science-fiction"],
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["tags"] == ["classique", "space-opera"]  # trié par nom
        assert data["genres"] == ["Science-fiction"]

    def test_patch_replace_tags_keeps_genres(self, client):
        """PATCH tags ne doit pas toucher aux genres (purge par kind)."""
        book = client.post("/api/v1/books", json={
            "title": "X",
            "tags": ["a"],
            "genres": ["g1"],
        }).json()

        resp = client.patch(f"/api/v1/books/{book['id']}", json={"tags": ["b"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tags"] == ["b"]
        assert data["genres"] == ["g1"]  # préservés

    def test_patch_empty_tags_clears_them(self, client):
        book = client.post("/api/v1/books", json={"title": "X", "tags": ["a"]}).json()
        resp = client.patch(f"/api/v1/books/{book['id']}", json={"tags": []})
        assert resp.json()["tags"] == []

    def test_labels_are_shared_by_name(self, client):
        """Le label 'fantasy' est réutilisé entre livres (table unique)."""
        client.post("/api/v1/books", json={"title": "A", "genres": ["fantasy"]})
        resp = client.post("/api/v1/books", json={"title": "B", "genres": ["fantasy"]})
        assert resp.status_code == 201

        labels = client.get("/api/v1/labels", params={"kind": "genre"}).json()
        fantasy = next(i for i in labels["items"] if i["name"] == "fantasy")
        assert fantasy["book_count"] == 2


class TestListFilters:
    def _seed(self, client):
        client.post("/api/v1/books", json={
            "title": "Dune", "authors": ["Frank Herbert"],
            "tags": ["space-opera"], "genres": ["SF"],
        })
        client.post("/api/v1/books", json={
            "title": "LOTR", "authors": ["Tolkien"],
            "genres": ["fantasy"],
        })
        client.post("/api/v1/books", json={
            "title": "1984", "authors": ["George Orwell"],
            "tags": ["space-opera"], "genres": ["SF"],
        })

    def test_filter_by_author(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"author": "Frank Herbert"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "Dune"

    def test_filter_by_tag(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"tag": "space-opera"})
        assert resp.json()["total"] == 2

    def test_filter_by_genre(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={"genre": "fantasy"})
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["title"] == "LOTR"

    def test_filter_by_owned(self, client):
        self._seed(client)
        client.post("/api/v1/books", json={"title": "Wish", "is_wishlist": 1})
        # owned=1 : la Bibliothèque (le wishlist, owned=0, est déjà exclu).
        resp = client.get("/api/v1/books", params={"owned": 1})
        assert resp.json()["total"] == 3
        # owned=0 n'existe pas en Bibliothèque ; en mode wishlist, si.
        resp = client.get("/api/v1/books", params={"owned": 0})
        assert resp.json()["total"] == 0
        resp = client.get("/api/v1/books", params={"wishlist": "true", "owned": 0})
        assert resp.json()["total"] == 1

    def test_combined_filters(self, client):
        self._seed(client)
        resp = client.get("/api/v1/books", params={
            "genre": "SF", "tag": "space-opera",
        })
        assert resp.json()["total"] == 2  # Dune + 1984

    def test_legacy_status_wishlist_matches_nothing(self, client):
        """L'ancien statut `wishlist` n'existe plus en base : le filtre ne
        ramène rien (les wishlist vivent sous is_wishlist=1)."""
        self._seed(client)
        client.post("/api/v1/books", json={"title": "Wish", "is_wishlist": 1})
        resp = client.get("/api/v1/books", params={"status": "wishlist"})
        assert resp.json()["total"] == 0


class TestStatus:
    def test_move_status(self, client):
        book = client.post("/api/v1/books", json={"title": "X"}).json()
        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "reading"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "reading"
        assert resp.json()["owned"] == 1

    def test_status_wishlist_rejected(self, client):
        """`wishlist` n'est plus un statut (16/08/2026) : la validation du
        schéma la refuse sur POST /books/{id}/status."""
        book = client.post("/api/v1/books", json={"title": "X"}).json()
        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "wishlist"})
        assert resp.status_code == 422
        # Le livre est resté inchangé.
        assert client.get(f"/api/v1/books/{book['id']}").json()["status"] == "tbr"

    def test_acquire_restores_owned_1(self, client):
        """La sortie de wishlist (POST /acquire) rend le livre possédé et le
        met en pile à lire — remplace l'ancien passage status->wishlist."""
        book = client.post("/api/v1/books", json={"title": "X", "is_wishlist": 1}).json()
        assert book["owned"] == 0
        resp = client.post(f"/api/v1/books/{book['id']}/acquire")
        assert resp.json()["owned"] == 1
        assert resp.json()["status"] == "tbr"

    def test_mark_read_creates_read_entry(self, client, db_engine):
        from sqlmodel import Session, select

        from app.models import ReadEntry

        book = client.post("/api/v1/books", json={"title": "X"}).json()
        resp = client.post(
            f"/api/v1/books/{book['id']}/status",
            json={"status": "read", "finished_at": "2026-08-14"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "read"

        with Session(db_engine) as session:
            entries = session.exec(
                select(ReadEntry).where(ReadEntry.book_id == book["id"])
            ).all()
            assert len(entries) == 1
            assert entries[0].finished_at == "2026-08-14"

    def test_mark_read_without_finished_at_defaults_today(self, client, db_engine):
        from datetime import date

        from sqlmodel import Session, select

        from app.models import ReadEntry

        book = client.post("/api/v1/books", json={"title": "X"}).json()
        client.post(f"/api/v1/books/{book['id']}/status", json={"status": "read"})
        with Session(db_engine) as session:
            entries = session.exec(
                select(ReadEntry).where(ReadEntry.book_id == book["id"])
            ).all()
            assert entries[0].finished_at == date.today().isoformat()

    def test_status_without_read_no_read_entry(self, client, db_engine):
        from sqlmodel import Session, select

        from app.models import ReadEntry

        book = client.post("/api/v1/books", json={"title": "X"}).json()
        client.post(f"/api/v1/books/{book['id']}/status", json={"status": "dnf"})
        with Session(db_engine) as session:
            entries = session.exec(
                select(ReadEntry).where(ReadEntry.book_id == book["id"])
            ).all()
            assert entries == []

    def test_invalid_status(self, client):
        book = client.post("/api/v1/books", json={"title": "X"}).json()
        resp = client.post(f"/api/v1/books/{book['id']}/status", json={"status": "périmé"})
        assert resp.status_code == 422

    def test_status_missing_book(self, client):
        resp = client.post("/api/v1/books/9999/status", json={"status": "read"})
        assert resp.status_code == 404


class TestTaxonomy:
    def _seed(self, client):
        client.post("/api/v1/books", json={
            "title": "Dune", "authors": ["Frank Herbert"], "genres": ["SF"],
        })
        client.post("/api/v1/books", json={
            "title": "Dune Messiah", "authors": ["Frank Herbert"], "genres": ["SF"],
        })

    def test_list_authors_with_counts(self, client):
        self._seed(client)
        resp = client.get("/api/v1/authors")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Frank Herbert"
        assert data[0]["book_count"] == 2

    def test_author_books(self, client):
        self._seed(client)
        authors = client.get("/api/v1/authors").json()
        resp = client.get(f"/api/v1/authors/{authors[0]['id']}/books")
        assert resp.status_code == 200
        data = resp.json()
        assert data["author"]["name"] == "Frank Herbert"
        assert {b["title"] for b in data["books"]} == {"Dune", "Dune Messiah"}

    def test_author_books_missing(self, client):
        assert client.get("/api/v1/authors/9999/books").status_code == 404

    def test_labels_by_kind(self, client):
        self._seed(client)
        client.post("/api/v1/books", json={"title": "X", "tags": ["pile"]})

        genres = client.get("/api/v1/labels", params={"kind": "genre"}).json()
        tags = client.get("/api/v1/labels", params={"kind": "tag"}).json()
        assert genres["total"] == 1
        assert genres["items"][0]["name"] == "SF"
        assert genres["items"][0]["book_count"] == 2
        assert tags["total"] == 1
        assert tags["items"][0]["kind"] == "tag"

    def test_labels_invalid_kind(self, client):
        resp = client.get("/api/v1/labels", params={"kind": "genre|tag"})
        assert resp.status_code == 422


class TestSeries:
    """Endpoints séries (décision produit 15/08) : filtre « Série » de la
    Bibliothèque et tri par numéro de tome."""

    def _seed(self, client):
        client.post("/api/v1/books", json={
            "title": "Dune", "series": "Les Dune", "series_index": 1,
        })
        client.post("/api/v1/books", json={
            "title": "Hors-série", "series": "Les Dune", "series_index": 1.5,
        })
        client.post("/api/v1/books", json={
            "title": "Dune Messiah", "series": "Les Dune", "series_index": 2,
        })

    def test_list_series_with_counts(self, client):
        self._seed(client)
        resp = client.get("/api/v1/series")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Les Dune"
        assert data[0]["book_count"] == 3

    def test_series_books_ordered_by_tome(self, client):
        self._seed(client)
        series = client.get("/api/v1/series").json()
        resp = client.get(f"/api/v1/series/{series[0]['id']}/books")
        assert resp.status_code == 200
        data = resp.json()
        assert data["series"]["name"] == "Les Dune"
        titles = [(b["title"], b["series_index"]) for b in data["books"]]
        assert titles == [
            ("Dune", 1),
            ("Hors-série", 1.5),  # décimales entre les tomes
            ("Dune Messiah", 2),
        ]

    def test_series_books_missing(self, client):
        assert client.get("/api/v1/series/9999/books").status_code == 404
