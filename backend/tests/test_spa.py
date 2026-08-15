"""Tests du catch-all SPA (backend/app/main.py).

Verrouille le comportement nécessaire au routage react-router : un
rechargement d'onglet sur un chemin profond (`/pile-a-lire`, `/livres/5`)
doit servir `index.html`, pas 404. Les routes API et /covers restent
prioritaires, et un chemin API inconnu renvoie bien 404 (pas le HTML du SPA).
"""

from pathlib import Path

from app import main as app_main


class TestSpaFallback:
    def _mount_static(self, monkeypatch, tmp_path: Path) -> Path:
        """Monte un dossier statique factice dans main.static_dir."""
        static = tmp_path / "static"
        static.mkdir()
        (static / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")
        (static / "assets").mkdir()
        (static / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
        monkeypatch.setattr(app_main, "static_dir", static)
        return static

    def test_health_prioritaire(self, client, tmp_path, monkeypatch):
        self._mount_static(monkeypatch, tmp_path)
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_racine_sert_index(self, client, tmp_path, monkeypatch):
        static = self._mount_static(monkeypatch, tmp_path)
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.text == (static / "index.html").read_text()

    def test_deep_link_sert_index(self, client, tmp_path, monkeypatch):
        """/pile-a-lire (route react-router) => index.html, pas 404."""
        static = self._mount_static(monkeypatch, tmp_path)
        for path in ("/pile-a-lire", "/livres/5", "/wishlist", "/reglages"):
            resp = client.get(path)
            assert resp.status_code == 200, path
            assert resp.text == (static / "index.html").read_text()

    def test_fichier_reel_servi(self, client, tmp_path, monkeypatch):
        self._mount_static(monkeypatch, tmp_path)
        resp = client.get("/assets/app.js")
        assert resp.status_code == 200
        assert resp.text == "console.log('ok')"

    def test_chemin_api_inconnu_404(self, client, tmp_path, monkeypatch):
        """Un chemin API inconnu ne doit pas retomber sur le HTML du SPA."""
        self._mount_static(monkeypatch, tmp_path)
        resp = client.get("/api/v1/bogus")
        assert resp.status_code == 404
        assert "html" not in resp.headers.get("content-type", "").lower()

    def test_front_non_construit_404(self, client, tmp_path, monkeypatch):
        static = tmp_path / "static"
        static.mkdir()  # pas d'index.html
        monkeypatch.setattr(app_main, "static_dir", static)
        resp = client.get("/pile-a-lire")
        assert resp.status_code == 404
