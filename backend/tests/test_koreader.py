"""Tests Phase 5 — import KOReader (statistics.sqlite3) (§4, §5).

Critère d'acceptation : « Upload d'un statistics.sqlite3 → sessions
importées sans doublon ; rattachement d'un livre persiste le koreader_md5. »

Les fichiers de test sont de vraies bases SQLite construites en dur avec le
schéma KOReader (table `book` + `page_stat_data` ou l'ancienne `page_stat`).
"""

import sqlite3
from pathlib import Path

import pytest

import app.config as config
from app.services.koreader import session_hash

#: Timestamps Unix de base (suffisants pour des assertions stables).
T0 = 1_700_000_000  # 2023-11-14T22:13:20+00:00


def _write_stats(path: Path, books, rows, stats_table="page_stat_data"):
    """Construit un statistics.sqlite3 de test (schéma KOReader de §4.1)."""
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE book (
            id INTEGER PRIMARY KEY, title TEXT, authors TEXT, notes TEXT,
            last_open INTEGER, highlights INTEGER, pages INTEGER, series TEXT,
            language TEXT, md5 TEXT, total_read_time INTEGER, total_read_pages INTEGER
        )
        """
    )
    conn.execute(
        f"""
        CREATE TABLE {stats_table} (
            id INTEGER PRIMARY KEY, id_book INTEGER, page INTEGER,
            start_time REAL, duration REAL, total_pages INTEGER
        )
        """
    )
    for book in books:
        if len(book) == 4:
            conn.execute(
                "INSERT INTO book (id, title, authors, md5) VALUES (?, ?, ?, ?)", book
            )
        else:
            conn.execute(
                "INSERT INTO book (id, title, authors, md5, total_read_time)"
                " VALUES (?, ?, ?, ?, ?)",
                book,
            )
    for row in rows:
        conn.execute(
            f"INSERT INTO {stats_table} (id_book, page, start_time, duration, total_pages)"
            " VALUES (?, ?, ?, ?, ?)",
            row,
        )
    conn.commit()
    conn.close()


def _upload(client, path: Path, filename="statistics.sqlite3"):
    return client.post(
        "/api/v1/koreader/import",
        files={"file": (filename, path.read_bytes(), "application/octet-stream")},
    )


def _make_book(client, title="Dune", page_count=400, koreader_md5=None):
    payload = {"title": title, "page_count": page_count}
    if koreader_md5:
        payload["koreader_md5"] = koreader_md5
    resp = client.post("/api/v1/books", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Import + preview
# ---------------------------------------------------------------------------

class TestImportPreview:
    def test_preview_rebuilds_one_session(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 11, T0 + 125, 100, 400),
                (1, 12, T0 + 230, 90, 400),
            ],
        )
        resp = _upload(client, path)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["gap_sec"] == 900
        assert data["sessions_to_import"] == 1
        assert data["sessions_skipped"] == 0
        assert len(data["sessions"]) == 1

        book = data["books"][0]
        assert book["title"] == "Dune"
        assert book["authors"] == "Frank Herbert"
        assert book["md5"] == "md5abc123"
        assert book["total_sessions"] == 1
        assert book["total_duration_sec"] == 120 + 100 + 90
        assert book["matched"] is False  # aucun livre app avec ce md5
        assert len(book["candidates"]) == 0  # aucune bibliothèque app

        session = data["sessions"][0]
        assert session["start_page"] == 10
        assert session["end_page"] == 12
        assert session["pages_read"] == 3
        assert session["duration_sec"] == 310
        assert session["already_imported"] is False
        assert session["koreader_hash"] == session_hash(1, session["started_at"])

    def test_gap_splits_sessions(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "SESSION_GAP_SEC", 60)
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "", None)],
            rows=[
                # Bloc 1 : pages 10-12, écart de 5 s entre pages.
                (1, 10, T0 + 1000, 120, 400),
                (1, 11, T0 + 1005, 100, 400),
                (1, 12, T0 + 1010, 90, 400),
                # Écart de 200 s avec le bloc précédent > seuil de 60 s.
                (1, 13, T0 + 1210, 110, 400),
                (1, 14, T0 + 1215, 95, 400),
            ],
        )
        resp = _upload(client, path)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["gap_sec"] == 60
        assert len(data["sessions"]) == 2
        assert data["sessions_to_import"] == 2

        first, second = data["sessions"]
        assert (first["start_page"], first["end_page"]) == (10, 12)
        assert (second["start_page"], second["end_page"]) == (13, 14)
        assert second["pages_read"] == 2
        assert first["started_at"] != second["started_at"]

    def test_old_schema_page_stat_accepted(self, client, tmp_path):
        """SPEC §4.1 : anciennes versions KOReader = table `page_stat`."""
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "1984", "George Orwell", None)],
            rows=[(1, 5, T0, 60, 300)],
            stats_table="page_stat",
        )
        resp = _upload(client, path)
        assert resp.status_code == 200, resp.text
        assert resp.json()["sessions_to_import"] == 1

    def test_invalid_file_rejected(self, client, tmp_path):
        path = tmp_path / "not_sqlite.sqlite3"
        path.write_text("je ne suis pas une base SQLite")
        resp = _upload(client, path)
        assert resp.status_code == 422

    def test_unknown_schema_rejected(self, client, tmp_path):
        """Une base SQLite qui n'est pas un statistics.sqlite3 KOReader."""
        path = tmp_path / "stats.sqlite3"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE anything (id INTEGER)")
        conn.commit()
        conn.close()
        resp = _upload(client, path)
        assert resp.status_code == 422
        assert "KOReader" in resp.json()["detail"]

    def test_wrong_extension_rejected(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=[], rows=[])
        resp = _upload(client, path, filename="stats.txt")
        assert resp.status_code == 422

    def test_empty_file_rejected(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        path.write_bytes(b"")
        resp = _upload(client, path)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Confirmation (import effectif)
# ---------------------------------------------------------------------------

class TestConfirm:
    def test_auto_match_by_md5_imports_sessions(self, client, tmp_path):
        book = _make_book(client, title="Dune", koreader_md5="md5dune")
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5dune")],
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 50, T0 + 400, 300, 400),
            ],
        )
        import_id = _upload(client, path).json()["import_id"]

        # Preview : rattachement automatique déjà détecté via le md5 persisté.
        preview = _upload(client, path).json()
        assert preview["books"][0]["matched"] is True
        assert preview["books"][0]["matched_book_id"] == book["id"]

        resp = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id, "mappings": [],
        })
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["sessions_added"] == 1
        assert result["books_matched"] == 1
        assert result["books_unmatched"] == 0

        # Session écrite avec source=koreader et progression du livre à jour.
        sessions = client.get(f"/api/v1/books/{book['id']}/sessions").json()["items"]
        assert len(sessions) == 1
        assert sessions[0]["source"] == "koreader"
        assert sessions[0]["start_page"] == 10
        assert sessions[0]["end_page"] == 50
        assert sessions[0]["pages_read"] == 41
        assert sessions[0]["koreader_hash"]

        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["current_page"] == 50
        assert book2["current_percent"] == 0.125

    def test_import_idempotent_no_duplicates(self, client, tmp_path):
        book = _make_book(client, koreader_md5="md5dune")
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5dune")],
            rows=[(1, 10, T0 + 0, 120, 400), (1, 11, T0 + 130, 100, 400)],
        )
        first = _upload(client, path).json()
        confirm = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": first["import_id"], "mappings": [],
        }).json()
        assert confirm["sessions_added"] == 1

        # Re-upload du même fichier : tout est déjà présent.
        second = _upload(client, path).json()
        assert second["sessions_to_import"] == 0
        assert second["sessions_skipped"] == 1
        assert second["sessions"][0]["already_imported"] is True

        confirm2 = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": second["import_id"], "mappings": [],
        }).json()
        assert confirm2["sessions_added"] == 0
        assert confirm2["sessions_skipped"] == 1

        # Toujours une seule session en base pour ce livre.
        sessions = client.get(f"/api/v1/books/{book['id']}/sessions").json()["items"]
        assert len(sessions) == 1

    def test_confirm_with_mapping_persists_md5(self, client, tmp_path):
        """§4.3 : la confirmation manuelle persiste koreader_md5 → les imports
        futurs deviennent 100 % automatiques."""
        book = _make_book(client, title="Dune")  # aucun koreader_md5
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5dune")],
            rows=[(1, 7, T0, 90, 400)],
        )
        import_id = _upload(client, path).json()["import_id"]

        # Livre non rattaché : candidat suggéré (titre identique → score 1.0).
        resp = client.get("/api/v1/koreader/unmatched", params={"import_id": import_id})
        assert resp.status_code == 200
        books = resp.json()
        assert len(books) == 1
        assert books[0]["title"] == "Dune"
        assert len(books[0]["candidates"]) == 1
        assert books[0]["candidates"][0]["book_id"] == book["id"]
        assert books[0]["candidates"][0]["score"] == 1.0

        confirm = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id,
            "mappings": [{"koreader_book_id": 1, "book_id": book["id"]}],
        }).json()
        assert confirm["sessions_added"] == 1
        assert confirm["books_matched"] == 1

        # Le lien est persisté sur le livre app.
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["koreader_md5"] == "md5dune"

        # Un re-upload matche maintenant tout seul, sans mapping.
        again = _upload(client, path).json()
        assert again["books"][0]["matched"] is True
        assert again["books"][0]["matched_book_id"] == book["id"]

    def test_confirm_missing_import_id(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=[(1, "Dune", "", None)], rows=[])
        _upload(client, path)
        resp = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": "f" * 64, "mappings": [],
        })
        assert resp.status_code == 404

    def test_confirm_rejects_path_traversal_import_id(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=[], rows=[])
        _upload(client, path)
        resp = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": "../../etc/passwd", "mappings": [],
        })
        assert resp.status_code == 404  # jamais une erreur de chemin

    def test_confirm_consumes_pending_file(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=[(1, "Dune", "", None)], rows=[])
        import_id = _upload(client, path).json()["import_id"]
        assert client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id, "mappings": [],
        }).status_code == 200
        # Le fichier pending est consommé : re-confirmer échoue proprement.
        assert client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id, "mappings": [],
        }).status_code == 404
        assert list(config.KOREADER_PENDING_DIR.glob("*.sqlite3")) == []

    def test_confirm_rejects_unknown_book_mapping(self, client, tmp_path):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=[(1, "Dune", "", None)], rows=[])
        import_id = _upload(client, path).json()["import_id"]
        resp = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id,
            "mappings": [{"koreader_book_id": 1, "book_id": 9999}],
        })
        assert resp.status_code == 422

    def test_book_without_md5_linked_by_mapping(self, client, tmp_path):
        """Un livre KOReader sans md5 peut être rattaché manuellement : les
        sessions s'importent, mais aucun md5 n'est persisté (il n'y en a pas)."""
        book = _make_book(client, title="Le Meilleur des Mondes")
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[(1, "Le Meilleur des Mondes", "Aldous Huxley", None)],
            rows=[(1, 3, T0, 45, 250)],
        )
        import_id = _upload(client, path).json()["import_id"]
        confirm = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id,
            "mappings": [{"koreader_book_id": 1, "book_id": book["id"]}],
        }).json()
        assert confirm["sessions_added"] == 1
        book2 = client.get(f"/api/v1/books/{book['id']}").json()
        assert book2["koreader_md5"] is None
        assert client.get(f"/api/v1/books/{book['id']}/sessions").json()["total"] == 1

    def test_unmatched_books_counted(self, client, tmp_path):
        """Un livre KOReader sans rattachement (ni mapping ni md5) reste
        compté non rattaché, et ses sessions ne sont pas importées."""
        _make_book(client, title="Dune")  # existe, mais aucun lien
        path = tmp_path / "stats.sqlite3"
        _write_stats(
            path,
            books=[
                (1, "Dune", "Frank Herbert", None),  # non mappé
                (2, "1984", "George Orwell", "md51984"),
            ],
            rows=[(1, 5, T0, 60, 400), (2, 9, T0, 40, 300)],
        )
        # Un book app lié au md5 de 1984.
        _make_book(client, title="1984", koreader_md5="md51984")

        import_id = _upload(client, path).json()["import_id"]
        confirm = client.post("/api/v1/koreader/import/confirm", json={
            "import_id": import_id, "mappings": [],
        }).json()
        assert confirm["books_matched"] == 1
        assert confirm["books_unmatched"] == 1
        assert confirm["sessions_added"] == 1  # seulement celles de 1984


# ---------------------------------------------------------------------------
# Auto-calibration de l'unité des durées (arbitrage Jordy, 15/08/2026)
# ---------------------------------------------------------------------------

class TestDurationCalibration:
    """`page_stat_data.duration` est en ms dans les versions récentes, en s
    dans les anciennes : on compare Σduration à `book.total_read_time`
    (référence du plugin stats) — ratio ≈ 1000 → ms → diviser par 1000."""

    def _preview_session(self, client, tmp_path, books, rows):
        path = tmp_path / "stats.sqlite3"
        _write_stats(path, books=books, rows=rows)
        resp = _upload(client, path)
        assert resp.status_code == 200, resp.text
        return resp.json()["sessions"][0]

    def test_duration_in_ms_calibrated(self, client, tmp_path):
        """duration en ms (120000, 100000), total_read_time en s (220) :
        ratio = 220000/220 = 1000 → divisé par 1000 → session de 220 s."""
        session = self._preview_session(
            client, tmp_path,
            books=[(1, "Dune", "Frank Herbert", None, 220)],
            rows=[
                (1, 10, T0 + 0, 120_000, 400),
                (1, 11, T0 + 130, 100_000, 400),
            ],
        )
        assert session["duration_sec"] == 220

    def test_duration_in_seconds_kept(self, client, tmp_path):
        """duration en secondes (120, 100), total_read_time en s (220) :
        ratio ≈ 1 → pas de correction."""
        session = self._preview_session(
            client, tmp_path,
            books=[(1, "Dune", "Frank Herbert", None, 220)],
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 11, T0 + 130, 100, 400),
            ],
        )
        assert session["duration_sec"] == 220

    def test_duration_without_total_time_defaults_seconds(self, client, tmp_path):
        """Pas de `total_read_time` exploitable → hypothèse SPEC §4.2 :
        secondes, sans correction."""
        session = self._preview_session(
            client, tmp_path,
            books=[(1, "Dune", "Frank Herbert", None)],  # total_read_time absent
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 11, T0 + 130, 100, 400),
            ],
        )
        assert session["duration_sec"] == 220

    def test_majority_wins_mixed_files(self):
        """Fichier mixte : la majorité des livres exploitables impose l'unité."""
        from app.services.koreader import KoreaderBook, PageStatRow, detect_duration_factor

        books = [
            KoreaderBook(id=1, title="a", authors="", md5=None, total_read_time=100),
            KoreaderBook(id=2, title="b", authors="", md5=None, total_read_time=100),
            KoreaderBook(id=3, title="c", authors="", md5=None, total_read_time=100),
        ]
        rows = [
            PageStatRow(1, 1, T0, 100_000, 100),  # ms → ratio ≈ 1000
            PageStatRow(2, 1, T0, 100_000, 100),
            PageStatRow(3, 1, T0, 100, 100),      # s → ratio ≈ 1
        ]
        assert detect_duration_factor(books, rows) == 0.001

    def test_ambiguous_ratio_defaults_seconds(self):
        from app.services.koreader import KoreaderBook, PageStatRow, detect_duration_factor

        books = [KoreaderBook(id=1, title="a", authors="", md5=None, total_read_time=100)]
        rows = [PageStatRow(1, 1, T0, 300, 100)]  # ratio 3 : ni ≈1 ni ≈1000
        assert detect_duration_factor(books, rows) == 1.0
