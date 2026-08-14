"""Tests Phase 4 — highlights (§5).

Critère d'acceptation Phase 4 : « Créer/éditer un highlight et le
retrouver par recherche. »
"""


def _make_book(client, title="Test", page_count=400):
    resp = client.post("/api/v1/books", json={"title": title, "page_count": page_count})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_highlight(client, book_id, text="Une citation", **extra):
    payload = {"text": text, **extra}
    resp = client.post(f"/api/v1/books/{book_id}/highlights", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCreateHighlight:
    def test_create_manual_highlight(self, client):
        book = _make_book(client)
        resp = client.post(f"/api/v1/books/{book['id']}/highlights", json={
            "text": "« L'avenir est déjà là. »",
            "note": "à relire",
            "page": 42,
            "chapter": "Chapitre 3",
            "color": "yellow",
            "highlighted_at": "2026-08-10T18:30:00",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["source"] == "manual"
        assert data["book_id"] == book["id"]
        assert data["book_title"] == book["title"]
        assert data["page"] == 42
        assert data["chapter"] == "Chapitre 3"
        assert data["color"] == "yellow"
        assert data["highlighted_at"] == "2026-08-10T18:30:00"
        assert data["created_at"]

    def test_create_requires_only_text(self, client):
        book = _make_book(client)
        resp = client.post(f"/api/v1/books/{book['id']}/highlights", json={"text": "Solo"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Solo"
        assert data["source"] == "manual"

    def test_create_missing_book(self, client):
        resp = client.post("/api/v1/books/9999/highlights", json={"text": "x"})
        assert resp.status_code == 404

    def test_create_rejects_blank_text(self, client):
        book = _make_book(client)
        assert client.post(
            f"/api/v1/books/{book['id']}/highlights", json={"text": "   "}
        ).status_code == 422
        assert client.post(
            f"/api/v1/books/{book['id']}/highlights", json={}
        ).status_code == 422

    def test_create_rejects_negative_page(self, client):
        book = _make_book(client)
        resp = client.post(
            f"/api/v1/books/{book['id']}/highlights",
            json={"text": "x", "page": -1},
        )
        assert resp.status_code == 422


class TestListByBook:
    def test_list_book_highlights_recent_first(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="ancien",
                        highlighted_at="2026-08-01T10:00:00")
        _make_highlight(client, book["id"], text="récent",
                        highlighted_at="2026-08-10T10:00:00")

        resp = client.get(f"/api/v1/books/{book['id']}/highlights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["items"][0]["text"] == "récent"
        assert data["items"][1]["text"] == "ancien"
        assert data["items"][0]["book_title"] == book["title"]

    def test_list_without_highlighted_at_uses_created_at(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="premier")
        _make_highlight(client, book["id"], text="second")
        resp = client.get(f"/api/v1/books/{book['id']}/highlights")
        data = resp.json()
        assert [h["text"] for h in data["items"]] == ["second", "premier"]

    def test_list_empty(self, client):
        book = _make_book(client)
        resp = client.get(f"/api/v1/books/{book['id']}/highlights")
        assert resp.json()["total"] == 0

    def test_list_missing_book(self, client):
        assert client.get("/api/v1/books/9999/highlights").status_code == 404


class TestUpdateDelete:
    def test_patch_highlight(self, client):
        book = _make_book(client)
        h = _make_highlight(client, book["id"], text="Avant")
        resp = client.patch(f"/api/v1/highlights/{h['id']}", json={
            "text": "Après", "note": "annoté", "page": 12, "color": "pink",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["text"] == "Après"
        assert data["note"] == "annoté"
        assert data["page"] == 12
        assert data["color"] == "pink"
        assert data["source"] == "manual"

    def test_patch_partial_keeps_other_fields(self, client):
        book = _make_book(client)
        h = _make_highlight(client, book["id"], text="Gardé", note="conservé", page=7)
        resp = client.patch(f"/api/v1/highlights/{h['id']}", json={"page": 8})
        data = resp.json()
        assert data["text"] == "Gardé"
        assert data["note"] == "conservé"
        assert data["page"] == 8

    def test_patch_missing(self, client):
        assert client.patch("/api/v1/highlights/9999", json={"text": "x"}).status_code == 404

    def test_patch_rejects_blank_text(self, client):
        book = _make_book(client)
        h = _make_highlight(client, book["id"])
        assert client.patch(
            f"/api/v1/highlights/{h['id']}", json={"text": "  "}
        ).status_code == 422

    def test_delete_highlight(self, client):
        book = _make_book(client)
        h = _make_highlight(client, book["id"])
        resp = client.delete(f"/api/v1/highlights/{h['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/books/{book['id']}/highlights").json()["total"] == 0

    def test_delete_missing(self, client):
        assert client.delete("/api/v1/highlights/9999").status_code == 404

    def test_delete_removes_highlights_of_deleted_book(self, client, db_engine):
        """ON DELETE CASCADE : supprimer le livre emporte ses citations."""
        book = _make_book(client)
        _make_highlight(client, book["id"], text="citée")
        assert client.delete(f"/api/v1/books/{book['id']}").status_code == 204

        # La ligne highlight doit être physiquement supprimée (cascade),
        # pas seulement masquée par la jointure du flux.
        from sqlmodel import Session, select

        from app.models import Highlight

        with Session(db_engine) as session:
            remaining = session.exec(select(Highlight)).all()
        assert remaining == []
        assert client.get("/api/v1/highlights").json()["total"] == 0


class TestGlobalFeed:
    def test_feed_aggregates_all_books_with_title(self, client):
        b1 = _make_book(client, title="Dune")
        b2 = _make_book(client, title="1984")
        _make_highlight(client, b1["id"], text="La peur tue l'esprit")
        _make_highlight(client, b2["id"], text="Big Brother vous regarde")

        resp = client.get("/api/v1/highlights")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        titles = {h["book_title"] for h in data["items"]}
        assert titles == {"Dune", "1984"}

    def test_search_matches_text(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="La psychohistoire prédit l'avenir")
        resp = client.get("/api/v1/highlights", params={"q": "psychohistoire"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["text"].startswith("La psychohistoire")

    def test_search_matches_note(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="courte", note="revoir cette scène")
        resp = client.get("/api/v1/highlights", params={"q": "cette scène"})
        assert resp.json()["total"] == 1

    def test_search_case_insensitive(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="Le Cercle des poètes disparus")
        resp = client.get("/api/v1/highlights", params={"q": "POÈTES"})
        assert resp.json()["total"] == 1

    def test_search_accent_insensitive(self, client):
        """Taper sans accents (« poetes ») trouve « poètes » : le LIKE natif
        de SQLite n'y arriverait pas, c'est le rôle de `unaccent`."""
        book = _make_book(client)
        _make_highlight(client, book["id"], text="Le Cercle des poètes disparus")
        resp = client.get("/api/v1/highlights", params={"q": "des poetes"})
        assert resp.json()["total"] == 1

    def test_search_no_match(self, client):
        book = _make_book(client)
        _make_highlight(client, book["id"], text="unique")
        resp = client.get("/api/v1/highlights", params={"q": "introuvable"})
        assert resp.json()["total"] == 0

    def test_search_escapes_like_wildcards(self, client):
        """`%` et `_` saisis par l'utilisateur restent littéraux."""
        book = _make_book(client)
        _make_highlight(client, book["id"], text="progression 100% atteinte")
        _make_highlight(client, book["id"], text="autre citation")

        resp = client.get("/api/v1/highlights", params={"q": "100%"})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["text"] == "progression 100% atteinte"

    def test_feed_filter_by_book(self, client):
        b1 = _make_book(client, title="Dune")
        b2 = _make_book(client, title="1984")
        _make_highlight(client, b1["id"], text="eau de vie")
        _make_highlight(client, b2["id"], text="sang de vie")

        resp = client.get("/api/v1/highlights", params={"book_id": b2["id"]})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["book_title"] == "1984"

    def test_feed_search_plus_book_filter(self, client):
        b1 = _make_book(client, title="Dune")
        b2 = _make_book(client, title="1984")
        _make_highlight(client, b1["id"], text="mentat")
        _make_highlight(client, b2["id"], text="mentat aussi")

        resp = client.get("/api/v1/highlights", params={"q": "mentat", "book_id": b2["id"]})
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["book_title"] == "1984"

    def test_feed_pagination(self, client):
        book = _make_book(client)
        for i in range(5):
            _make_highlight(client, book["id"], text=f"citation {i}")

        resp = client.get("/api/v1/highlights", params={"page": 1, "page_size": 2})
        data = resp.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

        resp2 = client.get("/api/v1/highlights", params={"page": 3, "page_size": 2})
        assert len(resp2.json()["items"]) == 1
