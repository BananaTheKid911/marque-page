"""Tests de GET /export et POST /import — sauvegarde/restauration (§5).

L'export est le filet de sûreté de la base NVMe (hors backup 3-2-1) : il
doit contenir TOUTES les données (format_version explicite pour une
restauration future) et les couvertures locales. L'import est son miroir :
RESTAURATION = remplacement complet, transactionnel, ids préservés —
tout échec de validation annule tout.
"""

import io
import json
import zipfile

from app import config


def _seed_library(client) -> dict:
    """Un livre complet (série, formats, achat, lu) + session + highlight + lecture."""
    book = client.post(
        "/api/v1/books",
        json={
            "title": "Dune",
            "authors": ["Frank Herbert"],
            "genres": ["Science-fiction"],
            "tags": ["traduit"],
            "series": "Les Dune",
            "series_index": 1,
            "formats": [{"type": "physique", "owned": True}],
            "price_paid": 12.99,
            "status": "read",
        },
    ).json()
    client.post(
        f"/api/v1/books/{book['id']}/sessions",
        json={
            "started_at": "2026-08-10T20:00:00",
            "duration_sec": 3600,
            "start_page": 10,
            "end_page": 60,
        },
    )
    client.post(
        f"/api/v1/books/{book['id']}/highlights",
        json={"text": "Le ver des sables.", "page": 40, "highlighted_at": "2026-08-10T21:00:00"},
    )
    client.post(
        f"/api/v1/books/{book['id']}/reads",
        json={"started_at": "2026-08-01", "finished_at": "2026-08-12", "rating": 5},
    )
    return book


def _make_zip(payload: dict) -> bytes:
    """Archive ZIP contenant un marquepage.json donné (pour les cas invalides)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("marquepage.json", json.dumps(payload))
    return buf.getvalue()


class TestExport:
    def _read_json(self, resp) -> dict:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            return json.loads(archive.read("marquepage.json"))

    def test_export_zip_structure(self, client):
        _seed_library(client)
        resp = client.get("/api/v1/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/zip")
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="marquepage-backup-')
        assert disposition.endswith('.zip"')

        data = self._read_json(resp)
        assert data["app"] == "marquepage"
        assert data["format_version"] == 1
        assert "exported_at" in data

        assert len(data["data"]["books"]) == 1
        book = data["data"]["books"][0]
        assert book["title"] == "Dune"
        assert book["authors"] == ["Frank Herbert"]
        assert book["genres"] == ["Science-fiction"]
        assert book["tags"] == ["traduit"]
        assert book["series_name"] == "Les Dune"
        assert book["formats"] == [{"type": "physique", "owned": True}]
        assert book["price_paid"] == 12.99
        assert data["data"]["series"] == [{"id": book["series_id"], "name": "Les Dune"}]

        assert len(data["data"]["sessions"]) == 1
        assert data["data"]["sessions"][0]["duration_sec"] == 3600
        assert data["data"]["sessions"][0]["pages_read"] == 50
        assert data["data"]["sessions"][0]["source"] == "manual"

        assert len(data["data"]["highlights"]) == 1
        assert data["data"]["highlights"][0]["text"] == "Le ver des sables."
        assert data["data"]["highlights"][0]["book_title"] == "Dune"

        assert len(data["data"]["reads"]) == 1
        assert data["data"]["reads"][0]["rating"] == 5.0
        assert data["data"]["reads"][0]["finished_at"] == "2026-08-12"

    def test_export_library_vide(self, client):
        resp = client.get("/api/v1/export")
        assert resp.status_code == 200
        data = self._read_json(resp)
        assert data["data"]["books"] == []
        assert data["data"]["sessions"] == []
        assert data["data"]["highlights"] == []
        assert data["data"]["reads"] == []
        assert data["data"]["series"] == []

    def test_export_embarque_les_couvertures(self, client, tmp_path, monkeypatch):
        """Les fichiers de couverture locaux sont dans l'archive (chemins
        relatifs conservés), et un dossier vide ne casse pas l'export."""
        covers_dir = tmp_path / "covers"
        (covers_dir / "1").mkdir(parents=True)
        (covers_dir / "1" / "full.jpg").write_bytes(b"full-image")
        (covers_dir / "1" / "thumb.jpg").write_bytes(b"thumb-image")
        monkeypatch.setattr(config, "COVERS_DIR", covers_dir)

        client.post("/api/v1/books", json={"title": "X"})
        resp = client.get("/api/v1/export")
        assert resp.status_code == 200
        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            names = archive.namelist()
        assert "covers/1/full.jpg" in names
        assert "covers/1/thumb.jpg" in names

    def test_export_rejoue_les_ids_de_lapi(self, client):
        """Le contenu du JSON reflète exactement ce que l'API sert (mêmes
        champs BookOut) : pas de deuxième vérité à maintenir."""
        book = _seed_library(client)
        api_book = client.get(f"/api/v1/books/{book['id']}").json()
        exported_book = self._read_json(client.get("/api/v1/export"))["data"]["books"][0]
        for field in (
            "id", "title", "authors", "genres", "tags", "series_name",
            "series_index", "formats", "price_paid", "purchased_at",
            "is_primary_reading", "tbr_rank", "current_page", "current_percent",
            "owned", "status", "cover_path",
        ):
            assert exported_book[field] == api_book[field], field


class TestRestore:
    def _export_payload(self, client) -> dict:
        resp = client.get("/api/v1/export")
        with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
            return json.loads(archive.read("marquepage.json"))

    def _restore(self, client, zip_bytes: bytes):
        return client.post(
            "/api/v1/import", files={"file": ("backup.zip", zip_bytes, "application/zip")}
        )

    def test_roundtrip_restaure_l_identique(self, client):
        _seed_library(client)
        export = client.get("/api/v1/export")

        resp = self._restore(client, export.content)
        assert resp.status_code == 200, resp.text
        summary = resp.json()
        assert summary["books"] == 1
        assert summary["sessions"] == 1
        assert summary["highlights"] == 1
        assert summary["reads"] == 1
        assert summary["series"] == 1
        assert summary["exported_at"]

        books = client.get("/api/v1/books").json()
        assert books["total"] == 1
        book = books["items"][0]
        assert book["title"] == "Dune"
        assert book["authors"] == ["Frank Herbert"]
        assert book["series_name"] == "Les Dune"
        assert book["formats"] == [{"type": "physique", "owned": True}]
        assert book["price_paid"] == 12.99
        sessions = client.get(f"/api/v1/books/{book['id']}/sessions").json()
        assert sessions["total"] == 1
        assert sessions["items"][0]["duration_sec"] == 3600
        highlights = client.get(f"/api/v1/books/{book['id']}/highlights").json()
        assert highlights["total"] == 1

    def test_remplace_les_donnees_existantes(self, client):
        """Restaurer = REMPLACER : un snapshot à 1 livre écrase une base à 2."""
        _seed_library(client)  # Dune
        export = client.get("/api/v1/export")
        client.post("/api/v1/books", json={"title": "Ancien"})
        assert client.get("/api/v1/books").json()["total"] == 2

        resp = self._restore(client, export.content)
        assert resp.status_code == 200
        books = client.get("/api/v1/books").json()
        assert books["total"] == 1
        assert books["items"][0]["title"] == "Dune"

    def test_restauration_vide_est_legitime(self, client):
        """Restaurer un backup vide (bibliothèque vide) vide la base."""
        empty_export = client.get("/api/v1/export").content  # bibliothèque encore vide
        _seed_library(client)
        assert client.get("/api/v1/books").json()["total"] == 1

        resp = self._restore(client, empty_export)
        assert resp.status_code == 200
        assert resp.json()["books"] == 0
        assert client.get("/api/v1/books").json()["total"] == 0

    def test_rejette_zip_invalide_sans_toucher_la_base(self, client):
        _seed_library(client)
        resp = self._restore(client, b"pas un zip")
        assert resp.status_code == 422
        assert client.get("/api/v1/books").json()["total"] == 1

    def test_rejette_marquepage_json_absent(self, client):
        _seed_library(client)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("autre.txt", "x")
        resp = self._restore(client, buf.getvalue())
        assert resp.status_code == 422
        assert client.get("/api/v1/books").json()["total"] == 1

    def test_rejette_format_version_inconnu(self, client):
        _seed_library(client)
        payload = self._export_payload(client)
        payload["format_version"] = 99
        resp = self._restore(client, _make_zip(payload))
        assert resp.status_code == 422
        assert "format_version" in resp.json()["detail"]
        # Rien n'a été supprimé : le refus précède toute modification.
        assert client.get("/api/v1/books").json()["total"] == 1

    def test_reference_incoherente_annule_tout(self, client):
        """Une session pointant vers un livre inexistant fait échouer
        l'insertion : rollback complet, la base d'origine est intacte."""
        _seed_library(client)
        payload = self._export_payload(client)
        payload["data"]["sessions"][0]["book_id"] = 9999
        resp = self._restore(client, _make_zip(payload))
        assert resp.status_code == 422
        assert client.get("/api/v1/books").json()["total"] == 1
        assert client.get("/api/v1/books/1/sessions").json()["total"] == 1

    def test_restaure_les_identifiants_d_origine(self, client):
        """Les ids sont préservés (couvertures `covers/<id>/…` recollent)."""
        book = _seed_library(client)
        original_id = book["id"]
        export = client.get("/api/v1/export")
        resp = self._restore(client, export.content)
        assert resp.status_code == 200
        restored = client.get("/api/v1/books").json()["items"][0]
        assert restored["id"] == original_id

    def test_extraire_les_couvertures(self, client, tmp_path, monkeypatch):
        covers_dir = tmp_path / "covers"
        monkeypatch.setattr(config, "COVERS_DIR", covers_dir)
        _seed_library(client)
        payload = self._export_payload(client)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("marquepage.json", json.dumps(payload))
            archive.writestr("covers/1/full.jpg", b"full")
            archive.writestr("covers/1/thumb.jpg", b"thumb")
        resp = self._restore(client, buf.getvalue())
        assert resp.status_code == 200
        assert resp.json()["covers_written"] == 2
        assert (covers_dir / "1" / "full.jpg").read_bytes() == b"full"
        assert (covers_dir / "1" / "thumb.jpg").read_bytes() == b"thumb"

    def test_zip_slip_ignore_les_chemins_sortants(self, client, tmp_path, monkeypatch):
        covers_dir = tmp_path / "covers"
        monkeypatch.setattr(config, "COVERS_DIR", covers_dir)
        _seed_library(client)
        payload = self._export_payload(client)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("marquepage.json", json.dumps(payload))
            archive.writestr("covers/../evil.txt", b"evil")  # sort de COVERS_DIR
            archive.writestr("covers/ok.jpg", b"ok")
        resp = self._restore(client, buf.getvalue())
        assert resp.status_code == 200
        assert resp.json()["covers_written"] == 1
        assert not (tmp_path / "evil.txt").exists()
        assert (covers_dir / "ok.jpg").read_bytes() == b"ok"
