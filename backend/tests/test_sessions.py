"""Tests Phase 3 — sessions, timer, lectures, progression, stats (§5).

Critère d'acceptation Phase 3 : « Une session ajoute durée + pages ;
marquer "lu" enregistre finished_at ; le dashboard affiche temps total
et timeline. »
"""


def _make_book(client, page_count=400, title="Test"):
    resp = client.post("/api/v1/books", json={"title": title, "page_count": page_count})
    assert resp.status_code == 201, resp.text
    return resp.json()


class TestCreateSession:
    def test_create_session_sets_progress(self, client):
        book = _make_book(client, page_count=400)
        resp = client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-14T10:00:00",
            "duration_sec": 1800,
            "start_page": 10,
            "end_page": 50,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["source"] == "manual"
        assert data["pages_read"] == 40  # end - start dérivé
        assert data["duration_sec"] == 1800

        # Progression du livre mise à jour : 50/400 = 0.125
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 50
        assert book2["current_percent"] == 0.125

    def test_session_without_pages_keeps_zero_percent(self, client):
        book = _make_book(client, page_count=400)
        resp = client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-14T10:00:00", "duration_sec": 900,
        })
        assert resp.status_code == 201
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 0
        assert book2["current_percent"] == 0

    def test_session_missing_book(self, client):
        resp = client.post("/api/v1/books/9999/sessions", json={
            "started_at": "2026-08-14T10:00:00", "duration_sec": 60,
        })
        assert resp.status_code == 404

    def test_progress_takes_max_end_page(self, client):
        book = _make_book(client, page_count=100)
        client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-10T10:00:00", "duration_sec": 600,
            "start_page": 0, "end_page": 30,
        })
        client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-11T10:00:00", "duration_sec": 600,
            "start_page": 30, "end_page": 80,
        })
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 80
        assert book2["current_percent"] == 0.8


class TestListUpdateDeleteSession:
    def test_list_sessions_newest_first(self, client):
        book = _make_book(client)
        client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-10T10:00:00", "duration_sec": 600,
        })
        client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-12T10:00:00", "duration_sec": 900,
        })
        resp = client.get(f"/api/v1/books/{book['id']}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["items"][0]["started_at"].startswith("2026-08-12")

    def test_patch_session_resyncs_progress(self, client):
        book = _make_book(client, page_count=100)
        s = client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-10T10:00:00", "duration_sec": 600,
            "start_page": 0, "end_page": 40,
        }).json()
        resp = client.patch(f"/api/v1/sessions/{s['id']}", json={"end_page": 60})
        assert resp.status_code == 200
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 60
        assert book2["current_percent"] == 0.6

    def test_delete_session_resyncs_progress(self, client):
        book = _make_book(client, page_count=100)
        s1 = client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-10T10:00:00", "duration_sec": 600,
            "end_page": 80,
        }).json()
        client.post(f"/api/v1/books/{book['id']}/sessions", json={
            "started_at": "2026-08-11T10:00:00", "duration_sec": 600,
            "end_page": 20,
        })
        assert client.get(f"/api/v1/books/{book['id']}").json()["current_page"] == 80

        resp = client.delete(f"/api/v1/sessions/{s1['id']}")
        assert resp.status_code == 204
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 20

    def test_patch_delete_missing(self, client):
        assert client.patch("/api/v1/sessions/9999", json={"note": "x"}).status_code == 404
        assert client.delete("/api/v1/sessions/9999").status_code == 404


class TestTimer:
    def test_start_stop_flow(self, client):
        book = _make_book(client, page_count=200)

        start = client.post("/api/v1/timer/start", json={"book_id": book["id"]})
        assert start.status_code == 201, start.text
        data = start.json()
        assert data["source"] == "timer"
        assert data["ended_at"] is None
        assert data["start_page"] == 0 or data["start_page"] is None

        stop = client.post("/api/v1/timer/stop", json={"book_id": book["id"], "end_page": 42})
        assert stop.status_code == 200, stop.text
        data = stop.json()
        assert data["ended_at"] is not None
        assert data["end_page"] == 42
        assert data["duration_sec"] >= 0

        # Progression mise à jour.
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 42
        assert book2["current_percent"] == 0.21

    def test_double_start_rejected(self, client):
        book = _make_book(client)
        client.post("/api/v1/timer/start", json={"book_id": book["id"]})
        resp = client.post("/api/v1/timer/start", json={"book_id": book["id"]})
        assert resp.status_code == 409

    def test_stop_without_start_rejected(self, client):
        book = _make_book(client)
        resp = client.post("/api/v1/timer/stop", json={"book_id": book["id"], "end_page": 5})
        assert resp.status_code == 409

    def test_timer_missing_book(self, client):
        assert client.post("/api/v1/timer/start", json={"book_id": 9999}).status_code == 404
        assert client.post("/api/v1/timer/stop", json={"book_id": 9999, "end_page": 1}).status_code == 404

    def test_open_session_persists_across_requests(self, client):
        """La session ouverte vit côté serveur : un stop ultérieur la retrouve."""
        book = _make_book(client)
        s = client.post("/api/v1/timer/start", json={"book_id": book["id"]}).json()
        stop = client.post("/api/v1/timer/stop", json={"book_id": book["id"], "end_page": 10})
        assert stop.status_code == 200
        assert stop.json()["id"] == s["id"]

    def test_timer_start_promotes_tbr_to_reading(self, client):
        """Chemin automatique n°1 (décision produit 15/08) : démarrer une
        session in-app fait quitter la Pile à lire au livre."""
        book = _make_book(client)  # status par défaut : tbr
        resp = client.post("/api/v1/timer/start", json={"book_id": book["id"]})
        assert resp.status_code == 201
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["status"] == "reading"

    def test_timer_start_keeps_non_tbr_status(self, client):
        """Seul `tbr` est promu automatiquement : un livre en pause reste
        `on_hold` (la reprise depuis `on_hold` est un chemin manuel)."""
        book = _make_book(client)
        client.patch(f"/api/v1/books/{book['id']}", json={"status": "on_hold"})
        resp = client.post("/api/v1/timer/start", json={"book_id": book["id"]})
        assert resp.status_code == 201
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["status"] == "on_hold"


class TestReads:
    def test_create_read_with_rating_syncs_book(self, client):
        book = _make_book(client)
        resp = client.post(f"/api/v1/books/{book['id']}/reads", json={
            "started_at": "2026-07-01", "finished_at": "2026-07-10",
            "rating": 4.5, "review": "Excellent",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["rating"] == 4.5
        assert data["review"] == "Excellent"

        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["rating"] == 4.5

    def test_latest_rating_wins(self, client):
        book = _make_book(client)
        client.post(f"/api/v1/books/{book['id']}/reads", json={
            "finished_at": "2026-07-01", "rating": 3.0,
        })
        client.post(f"/api/v1/books/{book['id']}/reads", json={
            "finished_at": "2026-07-20", "rating": 5.0,
        })
        assert client.get(f"/api/v1/books/{book['id']}").json()["rating"] == 5.0

    def test_delete_rated_read_resets_book_rating(self, client):
        book = _make_book(client)
        r = client.post(f"/api/v1/books/{book['id']}/reads", json={
            "finished_at": "2026-07-01", "rating": 4.0,
        }).json()
        assert client.get(f"/api/v1/books/{book['id']}").json()["rating"] == 4.0

        resp = client.delete(f"/api/v1/reads/{r['id']}")
        assert resp.status_code == 204
        assert client.get(f"/api/v1/books/{book['id']}").json()["rating"] is None

    def test_list_reads(self, client):
        book = _make_book(client)
        client.post(f"/api/v1/books/{book['id']}/reads", json={"finished_at": "2026-07-01"})
        client.post(f"/api/v1/books/{book['id']}/reads", json={"finished_at": "2026-07-20"})
        resp = client.get(f"/api/v1/books/{book['id']}/reads")
        assert resp.json()["total"] == 2
        assert resp.json()["items"][0]["finished_at"] == "2026-07-20"

    def test_reads_missing_book(self, client):
        assert client.get("/api/v1/books/9999/reads").status_code == 404
        assert client.post("/api/v1/books/9999/reads", json={}).status_code == 404

    def test_patch_delete_missing(self, client):
        assert client.patch("/api/v1/reads/9999", json={"review": "x"}).status_code == 404
        assert client.delete("/api/v1/reads/9999").status_code == 404


class TestStats:
    def _seed(self, client):
        b1 = _make_book(client, page_count=400, title="Dune")
        client.post(f"/api/v1/books/{b1['id']}/sessions", json={
            "started_at": "2026-08-10T10:00:00", "duration_sec": 1800,
            "start_page": 0, "end_page": 100,
        })
        client.post(f"/api/v1/books/{b1['id']}/sessions", json={
            "started_at": "2026-08-11T10:00:00", "duration_sec": 900,
            "start_page": 100, "end_page": 200,
        })
        client.post(f"/api/v1/books/{b1['id']}/status", json={
            "status": "read", "finished_at": "2026-08-12",
        })

        b2 = _make_book(client, page_count=200, title="1984")
        client.post(f"/api/v1/books/{b2['id']}/sessions", json={
            "started_at": "2026-08-12T20:00:00", "duration_sec": 3600,
            "start_page": 0, "end_page": 50,
        })

    def test_overview(self, client):
        self._seed(client)
        resp = client.get("/api/v1/stats/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_books"] == 2
        assert data["books_read"] == 1
        assert data["total_sessions"] == 3
        assert data["total_duration_sec"] == 1800 + 900 + 3600
        assert data["total_pages_read"] == 100 + 100 + 50

    def test_timeline_day(self, client):
        self._seed(client)
        resp = client.get("/api/v1/stats/timeline", params={"range": "day"})
        data = resp.json()
        assert len(data["points"]) == 3  # 10, 11, 12 août
        durations = {p["period"]: p["duration_sec"] for p in data["points"]}
        assert durations["2026-08-12"] == 3600  # la session de 1984

    def test_timeline_week(self, client):
        self._seed(client)
        resp = client.get("/api/v1/stats/timeline", params={"range": "week"})
        data = resp.json()
        assert len(data["points"]) == 1
        assert data["points"][0]["sessions"] == 3

    def test_timeline_month(self, client):
        self._seed(client)
        resp = client.get("/api/v1/stats/timeline", params={"range": "month"})
        data = resp.json()
        assert data["points"][0]["period"] == "2026-08"

    def test_timeline_invalid_range(self, client):
        assert client.get("/api/v1/stats/timeline", params={"range": "year"}).status_code == 422

    def test_by_genre(self, client):
        self._seed(client)
        book = client.get("/api/v1/books", params={"q": "Dune"}).json()["items"][0]
        client.patch(f"/api/v1/books/{book['id']}", json={"genres": ["SF"]})

        resp = client.get("/api/v1/stats/by-genre")
        data = resp.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["label"] == "SF"
        assert data["items"][0]["duration_sec"] == 2700

    def test_by_author(self, client):
        self._seed(client)
        resp = client.get("/api/v1/stats/by-author")
        data = resp.json()
        # Deux livres sans auteur : aucun bucket (les sessions sans auteur
        # ne sont pas regroupées).
        assert data["items"] == []

        client.patch("/api/v1/books/1", json={"authors": ["Frank Herbert"]})
        resp = client.get("/api/v1/stats/by-author")
        assert resp.json()["items"][0]["label"] == "Frank Herbert"
