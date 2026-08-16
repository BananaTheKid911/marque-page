"""Tests du watcher KOReader (dossier surveillé, §4.4 — décision 16/08).

Le watcher scrute `KOREADER_INBOX_DIR` et traite les `statistics.sqlite3`
qui y arrivent :
- tous les livres matchent par `koreader_md5` -> import automatique
  (sessions idempotentes par `koreader_hash`), fichier archivé ;
- un livre ne matche pas -> fichier déplacé vers le pending, l'écran de
  rattachement manuel prend le relais (aucun confirm implicite).

On test le traitement synchrone `_scan_once`/`_handle_file` — pas la boucle
asyncio elle-même (timing instable en CI, pas d'intérêt).
"""

import sqlite3
from pathlib import Path

import pytest

from app import config
from app.services.koreader_watcher import KoreaderWatcher, _PROCESSED_DIRNAME


def _write_stats(path: Path, books, rows, stats_table="page_stat_data"):
    """Construit un statistics.sqlite3 de test (même forme que test_koreader)."""
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


T0 = 1_800_000.0  # 2026-01-01 00:00 UTC en secondes epoch (approx.)


@pytest.fixture()
def watcher(tmp_path, monkeypatch, db_engine):
    """Watcher pointé sur des dossiers temporaires + la base fraîche du test.

    Le watcher s'exécute hors du flux de requêtes FastAPI : il reçoit une
    `session_factory` branchée sur `db_engine` (la même base que le client
    de test), sinon il écrirait dans la base globale du conftest.
    """
    from sqlmodel import Session

    inbox = tmp_path / "inbox"
    pending = tmp_path / "pending"
    inbox.mkdir()
    pending.mkdir()
    monkeypatch.setattr(config, "KOREADER_INBOX_DIR", inbox)
    monkeypatch.setattr(config, "KOREADER_PENDING_DIR", pending)

    def factory():
        return Session(db_engine)

    return KoreaderWatcher(inbox_dir=inbox, session_factory=factory), inbox, pending


class TestWatcherScan:
    def test_auto_import_when_all_matched(self, client, watcher):
        """Un fichier dont TOUS les livres matchent par md5 est importé."""
        w, inbox, _ = watcher
        # Le livre existe dans l'app avec le bon koreader_md5.
        resp = client.post(
            "/api/v1/books",
            json={"title": "Dune", "page_count": 400, "koreader_md5": "md5abc123"},
        )
        assert resp.status_code == 201, resp.text
        book_id = resp.json()["id"]

        path = inbox / "statistics.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 11, T0 + 130, 100, 400),
            ],
        )

        handled = w._scan_once()
        assert handled == 1

        # La session a été importée et le fichier archivé.
        sessions = client.get(f"/api/v1/books/{book_id}/sessions").json()
        assert sessions["total"] == 1
        assert sessions["items"][0]["source"] == "koreader"
        assert not path.exists()  # plus dans l'inbox
        processed = inbox / _PROCESSED_DIRNAME
        assert len(list(processed.glob("*.sqlite3"))) == 1

    def test_unmatched_book_goes_to_pending(self, client, watcher):
        """Un livre non rattaché -> fichier en pending, AUCUN confirm."""
        w, inbox, pending = watcher
        # Aucun livre dans l'app avec ce md5.
        path = inbox / "statistics.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[(1, 10, T0 + 0, 120, 400)],
        )

        handled = w._scan_once()
        assert handled == 1

        # Le fichier est dans le pending, pas importé.
        assert not path.exists()
        assert len(list(pending.glob("*.sqlite3"))) == 1
        # Aucune session créée (aucun livre ne matchait).
        books = client.get("/api/v1/books", params={"page_size": 100}).json()["items"]
        assert books == []

    def test_unmatched_book_then_manual_confirm(self, client, watcher):
        """Flux complet : watcher met en attente, la confirmation manuelle applique."""
        w, inbox, pending = watcher
        path = inbox / "statistics.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[
                (1, 10, T0 + 0, 120, 400),
                (1, 11, T0 + 130, 100, 400),
            ],
        )
        w._scan_once()

        # L'écran « Livres non rattachés » le voit (§4.3).
        import_id = list(pending.glob("*.sqlite3"))[0].stem
        unmatched = client.get("/api/v1/koreader/unmatched").json()
        assert len(unmatched) == 1
        assert unmatched[0]["md5"] == "md5abc123"

        # L'utilisateur crée le livre et le rattache.
        book = client.post(
            "/api/v1/books",
            json={"title": "Dune", "page_count": 400},
        ).json()
        confirm = client.post(
            "/api/v1/koreader/import/confirm",
            json={
                "import_id": import_id,
                "mappings": [{"koreader_book_id": 1, "book_id": book["id"]}],
            },
        )
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["sessions_added"] == 1
        # Le md5 est persisté : les prochains imports seront automatiques.
        refreshed = client.get(f"/api/v1/books/{book['id']}").json()
        assert refreshed["koreader_md5"] == "md5abc123"

    def test_idempotent_replay(self, client, watcher):
        """Rejouer le même fichier n'ajoute rien (dédup par koreader_hash)."""
        w, inbox, _ = watcher
        client.post(
            "/api/v1/books",
            json={"title": "Dune", "page_count": 400, "koreader_md5": "md5abc123"},
        )
        path = inbox / "statistics.sqlite3"
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[(1, 10, T0 + 0, 120, 400)],
        )

        w._scan_once()
        # On remet le même fichier (le sync suivant le re-pousse).
        _write_stats(
            path,
            books=[(1, "Dune", "Frank Herbert", "md5abc123")],
            rows=[(1, 10, T0 + 0, 120, 400)],
        )
        w._scan_once()

        books = client.get("/api/v1/books", params={"page_size": 100}).json()["items"]
        sessions = client.get(f"/api/v1/books/{books[0]['id']}/sessions").json()
        assert sessions["total"] == 1  # pas de doublon

    def test_invalid_file_stays_in_inbox(self, watcher):
        """Un fichier non-SQLite n'est pas importé ni déplacé."""
        w, inbox, _ = watcher
        path = inbox / "statistics.sqlite3"
        path.write_bytes(b"not a sqlite database at all")
        handled = w._scan_once()
        assert handled == 0
        assert path.exists()  # reste en place pour diagnostic
