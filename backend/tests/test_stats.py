"""Tests de GET /stats/overview — comptage wishlist (16/08/2026).

La wishlist se compte par `is_wishlist=1`, plus par le statut `wishlist`
(qui n'existe plus). La Pile à lire = `status='tbr'` HORS wishlist : un
livre souhaité a un status sans objet (forcé à 'tbr') qui ne compte pas
dans la PAL.
"""


def _seed(client):
    client.post("/api/v1/books", json={"title": "Lu", "status": "read"})
    client.post("/api/v1/books", json={"title": "En cours", "status": "reading"})
    client.post("/api/v1/books", json={"title": "Pile 1"})
    client.post("/api/v1/books", json={"title": "Pile 2"})
    client.post("/api/v1/books", json={"title": "Wish 1", "is_wishlist": 1})
    client.post("/api/v1/books", json={"title": "Wish 2", "is_wishlist": 1})


class TestStatsOverview:
    def test_wishlist_counted_by_is_wishlist(self, client):
        _seed(client)
        resp = client.get("/api/v1/stats/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_books"] == 6
        assert data["books_wishlist"] == 2
        # Les wishlist ont status='tbr' (sans objet) mais ne comptent pas
        # dans la Pile à lire (tbr ET is_wishlist=0).
        assert data["books_tbr"] == 2
        assert data["books_read"] == 1
        assert data["books_reading"] == 1

    def test_acquire_moves_book_from_wishlist_to_tbr(self, client):
        _seed(client)
        wish = client.get("/api/v1/books", params={"wishlist": "true"}).json()["items"][0]
        client.post(f"/api/v1/books/{wish['id']}/acquire")

        data = client.get("/api/v1/stats/overview").json()
        assert data["books_wishlist"] == 1
        assert data["books_tbr"] == 3  # la PAL récupère le livre acquis
