"""Router — sauvegarde (§5 : GET /export, POST /import).

`GET /export` est une fonctionnalité de SÛRETÉ, pas un confort : la base
SQLite et les couvertures vivent sur le NVMe local du MN56, hors backup
3-2-1 (qui ne protège que le NAS). L'export est le filet — il doit être
téléchargeable en un seul geste et contenir TOUT ce qui permet de
reconstruire l'app : les données (JSON complet, format_version pour les
restaurations futures) et les fichiers de couvertures locaux.

Format : archive ZIP `marquepage-backup-YYYY-MM-DD.zip` contenant :
- `marquepage.json`  — dump complet (books résolus, sessions, highlights,
  lectures, séries) au format_version 1 ;
- `covers/…`         — les fichiers de couverture tels qu'ils vivent dans
  COVERS_DIR, chemins relatifs conservés (restaurables tels quels).

`POST /import` est le miroir : il restaure une telle archive. RESTAURATION
= REMPLACEMENT : toutes les données existantes sont supprimées puis
réinsérées (ids préservés) dans une seule transaction — si l'archive est
invalide ou l'insertion échoue, rien ne change. Les couvertures sont
extraites après le commit de la base.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import config
from app.db import get_session
from app.models import (
    Author,
    Book,
    BookAuthor,
    BookFormat,
    BookLabel,
    Highlight,
    KoreaderImport,
    Label,
    ReadEntry,
    ReadingSession,
    Series,
)
from app.routers.books import (
    _book_out,
    _get_author_names,
    _get_labels,
    _replace_authors,
    _replace_formats,
    _replace_labels,
    _upsert_series,
)
from app.routers.highlights import _highlight_out
from app.routers.reads import _read_out
from app.routers.sessions import _session_out
from app.schemas import BookFormatIn, RestoreResult

router = APIRouter(tags=["sauvegarde"])

#: format_version lu par la restauration. Toute autre version = 422 avant
#: toute modification (un dump futur avec un nouveau format n'écrasera pas
#: des données sans un import capable de le lire).
SUPPORTED_FORMAT_VERSION = 1

#: Ordre de suppression pour la restauration : enfants avant parents
#: (foreign_keys=ON, on ne compte pas sur la cascade seule).
_RESTORE_DELETE_ORDER = (
    BookAuthor,
    BookLabel,
    BookFormat,
    ReadEntry,
    ReadingSession,
    Highlight,
    Book,
    Author,
    Label,
    Series,
    KoreaderImport,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_export_payload(session: Session) -> dict:
    """Dump complet des données, format_version 1.

    Les livres sont sérialisés via BookOut (taxonomie + formats + série
    résolus, comme l'API) : un export contient exactement ce que l'API
    sert, rien de plus. `cover_path` est conservé (chemin relatif) pour
    recoller les fichiers de `covers/` à la restauration.
    """
    books = session.exec(select(Book).order_by(Book.id)).all()
    series_rows = session.exec(select(Series).order_by(Series.id)).all()
    sessions = session.exec(select(ReadingSession).order_by(ReadingSession.id)).all()
    highlights = session.exec(select(Highlight).order_by(Highlight.id)).all()
    reads = session.exec(select(ReadEntry).order_by(ReadEntry.id)).all()

    titles = {b.id: b.title for b in books}

    books_out = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        books_out.append(_book_out(session, b, _get_author_names(session, b.id), tags, genres))

    return {
        "app": "marquepage",
        "format_version": 1,
        "exported_at": _now_iso(),
        "data": {
            "series": [{"id": s.id, "name": s.name} for s in series_rows],
            "books": [b.model_dump(mode="json") for b in books_out],
            "sessions": [s.model_dump(mode="json") for s in map(_session_out, sessions)],
            "highlights": [
                h.model_dump(mode="json")
                for h in (_highlight_out(x, titles.get(x.book_id)) for x in highlights)
            ],
            "reads": [r.model_dump(mode="json") for r in map(_read_out, reads)],
        },
    }


@router.get("/export")
def export_data(session: Session = Depends(get_session)) -> Response:
    """Archive ZIP complète : `marquepage.json` + `covers/`.

    Les couvertures sont des fichiers locaux (jamais de hotlink) : un
    backup qui les oublie perdrait les uploads manuels, irrécupérables.
    """
    payload = _build_export_payload(session)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "marquepage.json",
            json.dumps(payload, ensure_ascii=False, indent=2),
        )
        covers_dir = config.COVERS_DIR
        if covers_dir.is_dir():
            for path in sorted(covers_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=f"covers/{path.relative_to(covers_dir)}")

    filename = f"marquepage-backup-{date.today().isoformat()}.zip"
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Restauration (POST /import)
# ---------------------------------------------------------------------------

def _validate_backup_payload(payload: dict) -> None:
    """Vérifie que le JSON est un dump Marque-page lisible par CE build.

    Échoue (422) AVANT toute modification : un fichier inconnu ou un
    `format_version` futur ne doivent jamais écraser des données vivantes.
    """
    if not isinstance(payload, dict) or payload.get("app") != "marquepage":
        raise HTTPException(
            status_code=422, detail="Fichier de sauvegarde invalide : 'app' manquant ou inconnu"
        )
    version = payload.get("format_version")
    if version != SUPPORTED_FORMAT_VERSION:
        raise HTTPException(
            status_code=422,
            detail=(
                f"format_version {version!r} non supporté — ce build restaure "
                f"uniquement la version {SUPPORTED_FORMAT_VERSION}"
            ),
        )
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("books"), list):
        raise HTTPException(
            status_code=422, detail="Payload invalide : 'data.books' manquant ou non-liste"
        )


def _restore_data(session: Session, payload: dict) -> None:
    """Supprime tout puis réinsère les données de l'archive (ids préservés).

    Réutilise les helpers de création de books.py (`_replace_authors`,
    `_replace_labels`, `_replace_formats`, `_upsert_series`) : la
    restauration passe par EXACTEMENT le même chemin que la création par
    l'API — pas une deuxième implémentation de l'upsert taxonomie.
    L'appelant commit ; en cas d'échec, rollback = rien ne change.
    """
    data = payload["data"]

    for model in _RESTORE_DELETE_ORDER:
        session.exec(delete(model))

    # Séries d'abord : les livres y référencent par nom (même upsert qu'à
    # la création — les ids de série de l'archive ne sont pas préservés,
    # seule l'API les expose comme refs, et rien d'autre n'en dépend).
    for s in data.get("series", []):
        name = s.get("name")
        if isinstance(name, str) and name.strip():
            _upsert_series(session, name)

    for book_data in data["books"]:
        book = Book(
            id=book_data["id"],
            title=book_data["title"],
            subtitle=book_data.get("subtitle"),
            isbn10=book_data.get("isbn10"),
            isbn13=book_data.get("isbn13"),
            publisher=book_data.get("publisher"),
            published_date=book_data.get("published_date"),
            page_count=book_data.get("page_count"),
            language=book_data.get("language"),
            description=book_data.get("description"),
            cover_path=book_data.get("cover_path"),
            cover_source=book_data.get("cover_source"),
            status=book_data.get("status", "tbr"),
            owned=int(book_data.get("owned", 1)),
            rating=book_data.get("rating"),
            current_page=int(book_data.get("current_page", 0)),
            current_percent=float(book_data.get("current_percent", 0)),
            acquired_date=book_data.get("acquired_date"),
            series_index=book_data.get("series_index"),
            price_paid=book_data.get("price_paid"),
            purchased_at=book_data.get("purchased_at"),
            is_primary_reading=int(bool(book_data.get("is_primary_reading", False))),
            tbr_rank=book_data.get("tbr_rank"),
            tbr_note=book_data.get("tbr_note"),
            openlibrary_work=book_data.get("openlibrary_work"),
            openlibrary_edition=book_data.get("openlibrary_edition"),
            google_books_id=book_data.get("google_books_id"),
            koreader_md5=book_data.get("koreader_md5"),
            notes=book_data.get("notes"),
            created_at=book_data.get("created_at") or _now_iso(),
            updated_at=book_data.get("updated_at") or _now_iso(),
        )
        series_name = book_data.get("series_name")
        if isinstance(series_name, str) and series_name.strip():
            series = _upsert_series(session, series_name)
            if series is not None:
                book.series_id = series.id
        session.add(book)
        session.flush()  # book.id connu pour les liaisons

        _replace_authors(session, book, book_data.get("authors") or [])
        _replace_labels(session, book, book_data.get("tags"), book_data.get("genres"))
        formats = book_data.get("formats") or []
        if formats:
            _replace_formats(
                session,
                book,
                [BookFormatIn(type=f["type"], owned=f["owned"]) for f in formats],
            )

    for s in data.get("sessions", []):
        session.add(
            ReadingSession(
                id=s["id"],
                book_id=s["book_id"],
                started_at=s["started_at"],
                ended_at=s.get("ended_at"),
                duration_sec=s["duration_sec"],
                start_page=s.get("start_page"),
                end_page=s.get("end_page"),
                pages_read=s.get("pages_read"),
                note=s.get("note"),
                source=s.get("source", "manual"),
                koreader_hash=s.get("koreader_hash"),
                created_at=s.get("created_at") or _now_iso(),
            )
        )

    for h in data.get("highlights", []):
        session.add(
            Highlight(
                id=h["id"],
                book_id=h["book_id"],
                text=h["text"],
                note=h.get("note"),
                page=h.get("page"),
                location=h.get("location"),
                chapter=h.get("chapter"),
                color=h.get("color"),
                source=h.get("source", "manual"),
                highlighted_at=h.get("highlighted_at"),
                created_at=h.get("created_at") or _now_iso(),
            )
        )

    for r in data.get("reads", []):
        session.add(
            ReadEntry(
                id=r["id"],
                book_id=r["book_id"],
                started_at=r.get("started_at"),
                finished_at=r.get("finished_at"),
                rating=r.get("rating"),
                review=r.get("review"),
                created_at=r.get("created_at") or _now_iso(),
            )
        )


def _extract_covers(archive: zipfile.ZipFile) -> int:
    """Écrit les `covers/…` de l'archive dans COVERS_DIR.

    Défense zip-slip : tout chemin qui sortirait de COVERS_DIR (composant
    `..` ou chemin absolu) est ignoré. Retourne le nombre de fichiers
    écrits.
    """
    covers_dir = config.COVERS_DIR
    covers_dir.mkdir(parents=True, exist_ok=True)
    root = covers_dir.resolve()
    written = 0
    for info in archive.infolist():
        if not info.filename.startswith("covers/") or info.is_dir():
            continue
        rel = info.filename[len("covers/"):]
        if not rel:
            continue
        target = (covers_dir / rel).resolve()
        if target.parent != covers_dir and not str(target).startswith(str(root) + "/"):
            continue  # hors de COVERS_DIR : ignoré
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))
        written += 1
    return written


@router.post("/import", response_model=RestoreResult)
def restore_backup(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RestoreResult:
    """Restaure un backup `GET /export` (archive ZIP, multipart `file`).

    REMPLACEMENT complet : l'existant est supprimé et les données de
    l'archive réinsérées (ids préservés) dans UNE transaction — validation
    (422) et erreurs d'insertion annulent tout. Les couvertures sont
    extraites dans COVERS_DIR après le commit de la base (les fichiers ne
    sont pas transactionnels ; la base passe d'abord).
    """
    raw = file.file.read()
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise HTTPException(status_code=422, detail="Le fichier n'est pas une archive ZIP")

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if "marquepage.json" not in archive.namelist():
            raise HTTPException(
                status_code=422, detail="marquepage.json absent de l'archive"
            )
        try:
            payload = json.loads(archive.read("marquepage.json"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=422, detail="marquepage.json illisible") from exc

    _validate_backup_payload(payload)
    exported_at = payload.get("exported_at")

    try:
        _restore_data(session, payload)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Données de sauvegarde incohérentes — rien n'a été modifié",
        ) from exc

    # Couvertures APRÈS le commit : la base est restaurée même si un fichier
    # pose problème (on journalise, on ne fait pas échouer la restauration).
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        covers_written = _extract_covers(archive)

    data = payload["data"]
    return RestoreResult(
        exported_at=exported_at,
        books=len(data["books"]),
        sessions=len(data.get("sessions", [])),
        highlights=len(data.get("highlights", [])),
        reads=len(data.get("reads", [])),
        series=len(data.get("series", [])),
        covers_written=covers_written,
    )
