"""Tests de l'import Book Track — parser CSV (§4.6) + endpoint (§5).

Le fichier réel `booktracker.csv` (77 lignes, export de Jordy) est la
source de vérité : `parse_booktrack_csv` doit le parser intégralement sans
erreur. Les tests unitaires couvrent ensuite les cas particuliers du
format : RFC 4180 (retours à la ligne dans description), deux statuts
orthogonaux, tags `nom|||#couleur`, types multi-valeurs, dédup par id.
"""

from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.main import app
from app.routers import books as books_router
from app.services.booktrack import (
    BooktrackParseError,
    _map_status,
    _parse_tags,
    parse_booktrack_csv,
)
from tests.conftest import make_covers_client, override_http_deps

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_CSV = REPO_ROOT / "booktracker.csv"


def _jpeg_bytes(width=300, height=450) -> bytes:
    buf = __import__("io").BytesIO()
    Image.new("RGB", (width, height), (120, 60, 30)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Parser — fichier réel (source de vérité)
# ---------------------------------------------------------------------------

class TestParseRealFile:
    def test_parses_all_rows_of_real_export(self):
        raw = REAL_CSV.read_bytes()
        result = parse_booktrack_csv(raw)
        assert len(result.errors) == 0, result.errors
        assert len(result.rows) == 77

    def test_orthogonal_statuses(self):
        """state (possession) et readingStatus (lecture) sont indépendants."""
        result = parse_booktrack_csv(REAL_CSV.read_bytes())
        by_id = {r.booktrack_id: r for r in result.rows}
        # Annihilation : WISHLIST + reading -> wishlist prime (jamais lu dans l'app)
        annihil = by_id["C48313E0-D740-431A-BE59-9B573A2A8F83"]
        assert annihil.status == "wishlist"
        assert annihil.owned == 0
        # Blade Runner : NOT_OWNED + read -> lu mais non possédé
        blader = by_id["83571D46-01A1-4DF3-876D-39948D2DDB62"]
        assert blader.status == "read"
        assert blader.owned == 0
        # Batman : BOOKSHELF + to-read -> possédé, à lire
        batman = by_id["3BE0C914-C732-4446-82A8-08343C738825"]
        assert batman.status == "tbr"
        assert batman.owned == 1

    def test_tags_color_dropped(self):
        """Les tags arrivent sans leur couleur (`nom|||#couleur`)."""
        result = parse_booktrack_csv(REAL_CSV.read_bytes())
        by_id = {r.booktrack_id: r for r in result.rows}
        dune = by_id["4C78F4D4-F59F-4926-9888-5A4334FC7E53"]
        assert "Planet Opera" in dune.tags
        assert all("#" not in t for t in dune.tags)

    def test_multi_types(self):
        """`types` multi-valeurs séparées par `;` -> plusieurs formats."""
        result = parse_booktrack_csv(REAL_CSV.read_bytes())
        by_id = {r.booktrack_id: r for r in result.rows}
        kemetos = by_id["04052C3C-ABF5-47E8-8C2B-DB837CC8A607"]  # PAPERBACK;EBOOK
        types = {f.type for f in kemetos.formats}
        assert types == {"physique", "digital"}

    def test_multiline_description_handled(self):
        """La description multi-lignes (RFC 4180) ne casse pas le parse."""
        result = parse_booktrack_csv(REAL_CSV.read_bytes())
        by_id = {r.booktrack_id: r for r in result.rows}
        arrêtez = by_id["838BECB0-2100-42EC-960F-123133B0AE45"]
        assert arrêtez.description and "second cerveau" in arrêtez.description
        assert "\n" in arrêtez.description  # le retour à la ligne est conservé

    def test_read_entry_dates(self):
        result = parse_booktrack_csv(REAL_CSV.read_bytes())
        by_id = {r.booktrack_id: r for r in result.rows}
        blader = by_id["83571D46-01A1-4DF3-876D-39948D2DDB62"]
        assert blader.read_started_at == "2024-11-20"
        assert blader.read_finished_at == "2024-11-27"


# ---------------------------------------------------------------------------
# Parser — cas particuliers unitaires
# ---------------------------------------------------------------------------

class TestParserEdgeCases:
    def test_map_status_wishlist_wins(self):
        assert _map_status("WISHLIST", "read") == ("wishlist", 0)
        assert _map_status("WISHLIST", "") == ("wishlist", 0)

    def test_map_status_unknown_reading_status_defaults_tbr(self):
        assert _map_status("BOOKSHELF", "quelque-chose") == ("tbr", 1)

    def test_map_status_not_owned(self):
        assert _map_status("NOT_OWNED", "read") == ("read", 0)

    def test_parse_tags_color_dropped(self):
        raw = "Cyberpunk|||#DB34F2;Megacorporations|||#00D2E0"
        assert _parse_tags(raw) == ["Cyberpunk", "Megacorporations"]

    def test_empty_csv_rejected(self):
        with pytest.raises(BooktrackParseError):
            parse_booktrack_csv(b"")

    def test_missing_header_rejected(self):
        with pytest.raises(BooktrackParseError):
            parse_booktrack_csv(b"title,author\nfoo,bar\n")

    def test_row_without_id_reported_not_fatal(self):
        # 43 colonnes correctes mais id vide -> erreur de ligne, pas globale
        header = (
            "createdAt,updatedAt,id,externalId,source,title,subtitle,externalLink,state,"
            "types,isbn10,isbn13,releaseDate,originalReleaseDate,releaseYear,"
            "originalReleaseYear,placeOfPublication,description,remoteImageUrl,"
            "thumbnailRemoteImageUrl,externalAverageRating,userRating,pages,"
            "audiobookDuration,languages,purchaseDate,purchasePrice,purchaseCurrency,"
            "series,seriesNumber,location,bookcase,shelf,authors,narrators,illustrators,"
            "translators,publishers,categories,tags,readingStatus,startReading,endReading"
        )
        row = ",".join([""] * 43).replace(",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,",
                                          ",,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,,")
        # id à l'index 2 : on injecte une ligne vide
        empty_row = ",".join([""] * 43)
        result = parse_booktrack_csv(f"{header}\n{empty_row}\n".encode())
        assert len(result.rows) == 0
        assert len(result.errors) == 1
        assert "id" in result.errors[0][1]


# ---------------------------------------------------------------------------
# Endpoint — import réel
# ---------------------------------------------------------------------------

class TestImportEndpoint:
    @pytest.fixture(autouse=True)
    def _mock_http(self):
        """Tous les imports passent par un client HTTP mocké (aucun réseau).

        Le `get_http_client` de books.py est un singleton fermé par le
        lifespan du premier TestClient — sans override, chaque test d'import
        tenterait de vrais appels réseau et planterait dès que le singleton
        est fermé. L'override par défaut sert une image ; les tests qui
        veulent un autre comportement le remplacent via `override_http_deps`.
        """
        img = _jpeg_bytes()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=img, headers={"content-type": "image/jpeg"})

        override_http_deps(handler)
        yield
        # Cleanup : retire l'override posé par ce test (même si le test a
        # ré-utilisé override_http_deps, le handler pointé est le nôtre).
        app.dependency_overrides.pop(books_router.get_http_client, None)

    def _upload(self, client, content: bytes, filename="booktracker.csv"):
        return client.post(
            "/api/v1/import/booktrack",
            files={"file": (filename, content, "text/csv")},
        )

    def test_import_real_export(self, client):
        resp = self._upload(client, REAL_CSV.read_bytes())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["rows_parsed"] == 77
        assert data["books_created"] == 77
        assert data["books_skipped"] == 0
        assert data["line_errors"] == []

        # La bibliothèque contient les livres avec leurs métadonnées.
        books = client.get("/api/v1/books", params={"page_size": 100}).json()["items"]
        assert len(books) == 77
        dune = next(b for b in books if b["title"] == "Dune #01 Éd. Collector")
        assert dune["series_name"] == "Dune"
        assert dune["series_index"] is None  # seriesNumber vide dans le CSV réel
        assert dune["status"] == "read"
        assert dune["owned"] == 1
        assert "Planet Opera" in dune["tags"]

    def test_reimport_dedup_by_id(self, client):
        """Rejouer le même export ne crée AUCUN doublon (dédup par id)."""
        raw = REAL_CSV.read_bytes()
        first = self._upload(client, raw).json()
        assert first["books_created"] == 77

        second = self._upload(client, raw).json()
        assert second["books_created"] == 0
        assert second["books_skipped"] == 77

        books = client.get("/api/v1/books", params={"page_size": 100}).json()["items"]
        assert len(books) == 77

    def test_wishlist_books_have_no_price(self, client):
        resp = self._upload(client, REAL_CSV.read_bytes())
        assert resp.status_code == 200
        books = client.get("/api/v1/books", params={"status": "wishlist", "page_size": 100}).json()["items"]
        assert len(books) == 37
        for b in books:
            assert b["owned"] == 0
            assert b["price_paid"] is None
            assert b["purchased_at"] is None

    def test_cover_downloaded_locally(self, client, tmp_path, monkeypatch):
        """Une couverture Book Track est téléchargée localement (jamais hotlink)."""
        import app.services.covers as covers_service

        covers_dir = tmp_path / "covers"
        covers_dir.mkdir()
        monkeypatch.setattr(covers_service.config, "COVERS_DIR", covers_dir)

        resp = self._upload(client, REAL_CSV.read_bytes())
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["covers_downloaded"] > 0
        assert data["covers_failed"] == 0

        # Les fichiers sont servis depuis /covers (aucune URL distante).
        books = client.get("/api/v1/books", params={"page_size": 100}).json()["items"]
        with_cover = [b for b in books if b["cover_url"]]
        assert len(with_cover) == data["covers_downloaded"]
        for b in with_cover:
            assert b["cover_url"].startswith("/covers/")

    def test_non_csv_rejected(self, client):
        resp = self._upload(client, b"not a csv at all", filename="data.txt")
        assert resp.status_code == 422

    def test_empty_file_rejected(self, client):
        resp = self._upload(client, b"", filename="booktracker.csv")
        assert resp.status_code == 422
