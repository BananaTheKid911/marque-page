"""Router — import KOReader (statistics.sqlite3) (§4, Phase 5).

Flux en trois temps, conforme à §5 :
1. `POST /koreader/import` (multipart) → parse + reconstruction + diff preview.
   Le fichier est conservé dans `KOREADER_PENDING_DIR` sous `{sha256}.sqlite3` ;
   `import_id` = ce sha256.
2. L'utilisateur confirme les rattachements sur l'écran « Livres KOReader
   non rattachés » (§4.3).
3. `POST /koreader/import/confirm` ré-applique le tout : sessions manquantes
   créées (idempotence par `koreader_hash`), `koreader_md5` persisté sur les
   livres rattachés, journal `koreader_import`. Le fichier pending est ensuite
   supprimé — un confirm n'est valable qu'une fois.

Sécurité : le fichier uploadé est un fichier arbitraire. Il est ouvert en
lecture seule par le parser, jamais exécuté ; `import_id` est validé en
hexadécimal avant d'être utilisé dans un chemin ; aucune valeur du fichier
n'entre dans une requête SQL (SQLModel paramétré).
"""

from __future__ import annotations

import hashlib
import os
import re
from difflib import SequenceMatcher
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlmodel import Session, select

from app import config
from app.db import get_session, unaccent
from app.models import Author, Book, BookAuthor, KoreaderImport, ReadingSession
from app.routers.sessions import mark_started_reading, sync_book_progress
from app.schemas import (
    KoreaderBookPreview,
    KoreaderCandidate,
    KoreaderConfirmRequest,
    KoreaderConfirmResult,
    KoreaderPreview,
    KoreaderSessionPreview,
)
from app.services.koreader import (
    KoreaderError,
    KoreaderStats,
    detect_duration_factor,
    parse_statistics,
    sessions_by_book,
)

router = APIRouter(prefix="/koreader", tags=["koreader"])

_IMPORT_ID_RE = re.compile(r"^[0-9a-f]{64}$")  # sha256 hex


def _valid_import_id(value: str) -> bool:
    return bool(_IMPORT_ID_RE.match(value))


def _pending_path(import_id: str) -> Path:
    return config.KOREADER_PENDING_DIR / f"{import_id}.sqlite3"


# ---------------------------------------------------------------------------
# Matching (§4.3) — md5 exact d'abord, flou titre+auteur ensuite
# ---------------------------------------------------------------------------

def _split_authors(raw: str) -> list[str]:
    return [unaccent(p).strip() for p in re.split(r"[,;&]+", raw) if p.strip()]


def _candidate_score(k_title: str, k_authors: list[str], a_title: str, a_authors: list[str]) -> float:
    """Similarité 0..1 entre un livre KOReader et un livre de l'app.

    Base = ratio de similarité sur les titres normalisés (casse + accents
    neutralisés via `unaccent`) ; un auteur commun ajoute +0.15 (plafonné).
    Le titre identique est noté 1.0.
    """
    nk = unaccent(k_title).strip()
    na = unaccent(a_title).strip()
    if not nk or not na:
        return 0.0
    base = 1.0 if nk == na else SequenceMatcher(None, nk, na).ratio()
    if base < 0.5:
        return round(base, 3)
    for ka in k_authors:
        if ka and ka in a_authors:
            base = min(1.0, base + 0.15)
            break
    return round(base, 3)


def _app_author_names(session: Session, book_id: int) -> list[str]:
    rows = session.exec(
        select(Author.name)
        .join(BookAuthor, BookAuthor.author_id == Author.id)
        .where(BookAuthor.book_id == book_id)
        .order_by(Author.name)
    ).all()
    return list(rows)


def _build_book_previews(
    session: Session, stats: KoreaderStats, gap_sec: int, duration_factor: float
) -> list[KoreaderBookPreview]:
    """Un `KoreaderBookPreview` par livre du fichier.

    Rattachement auto uniquement par `koreader_md5` déjà persisté — jamais
    par le flou seul (SPEC §4.3 : le partial md5 interdit tout match
    aveugle). Les candidats flous sont des suggestions pour l'écran de
    confirmation.
    """
    app_books = session.exec(select(Book)).all()
    by_md5 = {b.koreader_md5: b for b in app_books if b.koreader_md5}
    author_names = {b.id: _app_author_names(session, b.id) for b in app_books}
    rebuilt = sessions_by_book(stats.rows, gap_sec, duration_factor)

    previews: list[KoreaderBookPreview] = []
    for kb in stats.books:
        book_sessions = rebuilt.get(kb.id, [])
        preview = KoreaderBookPreview(
            koreader_book_id=kb.id,
            title=kb.title,
            authors=kb.authors,
            md5=kb.md5,
            total_sessions=len(book_sessions),
            total_duration_sec=sum(s.duration_sec for s in book_sessions),
        )
        if kb.md5 and kb.md5 in by_md5:
            preview.matched = True
            preview.matched_book_id = by_md5[kb.md5].id
        else:
            k_authors = _split_authors(kb.authors)
            scored = [
                (_candidate_score(kb.title, k_authors, b.title, author_names[b.id]), b)
                for b in app_books
            ]
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, b in scored[:3]:
                if score >= 0.5:
                    preview.candidates.append(
                        KoreaderCandidate(
                            book_id=b.id,
                            title=b.title,
                            authors=author_names[b.id],
                            score=score,
                        )
                    )
        previews.append(preview)
    return previews


def _existing_hashes(session: Session) -> set[str]:
    """Hash des sessions KOReader déjà en base (idempotence §4.2).

    `session.exec` scalairise un select d'une seule colonne : les rows sont
    les valeurs directement, pas des tuples.
    """
    rows = session.exec(
        select(ReadingSession.koreader_hash).where(ReadingSession.koreader_hash.is_not(None))
    ).all()
    return set(rows)


def _session_previews(
    session: Session, rebuilt: dict[int, list]
) -> list[KoreaderSessionPreview]:
    existing = _existing_hashes(session)
    out: list[KoreaderSessionPreview] = []
    for book_id in sorted(rebuilt):
        for s in rebuilt[book_id]:
            out.append(
                KoreaderSessionPreview(
                    koreader_hash=s.koreader_hash,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    duration_sec=s.duration_sec,
                    start_page=s.start_page,
                    end_page=s.end_page,
                    pages_read=s.pages_read,
                    already_imported=s.koreader_hash in existing,
                )
            )
    return out


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/import", response_model=KoreaderPreview)
async def import_koreader(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> KoreaderPreview:
    """Upload du statistics.sqlite3 → diff preview (aucune écriture en base)."""
    if file.filename and not file.filename.lower().endswith((".sqlite3", ".sqlite", ".db")):
        raise HTTPException(
            status_code=422,
            detail="le fichier doit être une base SQLite (statistics.sqlite3)",
        )

    pending_dir = config.KOREADER_PENDING_DIR
    pending_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    size = 0
    tmp_path = pending_dir / "upload.tmp"
    try:
        with tmp_path.open("wb") as fh:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_KOREADER_BYTES:
                    raise HTTPException(
                        status_code=413, detail="fichier trop volumineux (max 50 Mo)"
                    )
                digest.update(chunk)
                fh.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="fichier vide")
        dest = _pending_path(digest.hexdigest())
        os.replace(tmp_path, dest)  # idempotent : un re-upload écrase le même hash
    finally:
        tmp_path.unlink(missing_ok=True)

    # Mono-utilisateur : un seul import pending à la fois.
    for old in pending_dir.glob("*.sqlite3"):
        if old != dest:
            old.unlink(missing_ok=True)

    try:
        stats = parse_statistics(dest)
    except KoreaderError as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    gap_sec = config.SESSION_GAP_SEC
    duration_factor = detect_duration_factor(stats.books, stats.rows)
    rebuilt = sessions_by_book(stats.rows, gap_sec, duration_factor)
    session_previews = _session_previews(session, rebuilt)
    to_import = sum(1 for s in session_previews if not s.already_imported)

    return KoreaderPreview(
        import_id=dest.stem,
        gap_sec=gap_sec,
        books=_build_book_previews(session, stats, gap_sec, duration_factor),
        sessions=session_previews,
        sessions_to_import=to_import,
        sessions_skipped=len(session_previews) - to_import,
    )


@router.post("/import/confirm", response_model=KoreaderConfirmResult)
def confirm_import(
    payload: KoreaderConfirmRequest,
    session: Session = Depends(get_session),
) -> KoreaderConfirmResult:
    """Applique l'import prévisualisé : sessions manquantes + rattachements.

    Idempotence : les sessions dont le `koreader_hash` existe déjà en base
    sont sautées — ré-importer le même fichier n'ajoute jamais rien.
    """
    if not _valid_import_id(payload.import_id):
        raise HTTPException(
            status_code=404, detail="Import inconnu ou expiré (re-uploader le fichier)"
        )
    path = _pending_path(payload.import_id)
    if not path.exists():
        raise HTTPException(
            status_code=404, detail="Import inconnu ou expiré (re-uploader le fichier)"
        )

    explicit: dict[int, int] = {}
    for mapping in payload.mappings:
        if session.get(Book, mapping.book_id) is None:
            raise HTTPException(
                status_code=422, detail=f"book_id {mapping.book_id} introuvable"
            )
        explicit[mapping.koreader_book_id] = mapping.book_id

    try:
        stats = parse_statistics(path)
    except KoreaderError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    result = apply_koreader_import(session, stats, explicit, file_sha256=payload.import_id)
    session.commit()

    # Import consommé : le fichier pending ne sert plus à rien.
    path.unlink(missing_ok=True)

    return KoreaderConfirmResult(
        import_id=payload.import_id,
        sessions_added=result.sessions_added,
        sessions_skipped=result.sessions_skipped,
        books_matched=result.books_matched,
        books_unmatched=result.books_unmatched,
    )


def apply_koreader_import(
    session: Session,
    stats: KoreaderStats,
    explicit: dict[int, int] | None = None,
    file_sha256: str = "watcher",
) -> KoreaderConfirmResult:
    """Applique un import KOReader sur la base : sessions + rattachements.

    Logique partagée entre POST /koreader/import/confirm (rattachements
    choisis par l'utilisateur) et le watcher du dossier surveillé (auto-
    rattachement par `koreader_md5` uniquement — jamais le flou seul, §4.3).
    `explicit` mappe `koreader_book_id -> book_id` (choix manuel) ; absent
    ou vide, seuls les livres déjà rattachés par `koreader_md5` matchent.
    Idempotence par `koreader_hash` : rejouer le même fichier n'ajoute rien.
    `file_sha256` est journalisé dans `koreader_import` (le watcher le
    calcule lui-même, l'API confirme celui de l'upload).

    L'appelant commit ; un rollback laisse la base inchangée.
    """
    app_books = session.exec(select(Book)).all()
    by_md5 = {b.koreader_md5: b for b in app_books if b.koreader_md5}
    existing = _existing_hashes(session)

    rebuilt = sessions_by_book(stats.rows, config.SESSION_GAP_SEC, detect_duration_factor(stats.books, stats.rows))
    total_sessions = sum(len(v) for v in rebuilt.values())

    explicit = explicit or {}
    sessions_added = 0
    linked_book_ids: set[int] = set()  # id_book KOReader rattachés

    for kb in stats.books:
        book_app = None
        target = explicit.get(kb.id)
        if target is not None:
            book_app = session.get(Book, target)
            linked_book_ids.add(kb.id)
        elif kb.md5 and kb.md5 in by_md5:
            book_app = by_md5[kb.md5]
            linked_book_ids.add(kb.id)
        if book_app is None:
            continue

        # Persiste le lien (SPEC §4.3) : les imports futurs matcheront seuls.
        if kb.md5 and book_app.koreader_md5 != kb.md5:
            book_app.koreader_md5 = kb.md5
            session.add(book_app)

        for s in rebuilt.get(kb.id, []):
            if s.koreader_hash in existing:
                continue
            session.add(
                ReadingSession(
                    book_id=book_app.id,
                    started_at=s.started_at,
                    ended_at=s.ended_at,
                    duration_sec=s.duration_sec,
                    start_page=s.start_page,
                    end_page=s.end_page,
                    pages_read=s.pages_read,
                    source="koreader",
                    koreader_hash=s.koreader_hash,
                )
            )
            sessions_added += 1
            # Chemin automatique n°2 vers `reading` (décision produit 15/08) :
            # un import apportant des sessions pour un livre encore `tbr` le
            # fait passer en lecture. Uniquement si des sessions NOUVELLES
            # sont ajoutées : re-importer le même fichier ne rebascule rien.
            mark_started_reading(book_app)
        sync_book_progress(session, book_app)

    books_matched = len(linked_book_ids)
    books_unmatched = len(stats.books) - books_matched

    session.add(
        KoreaderImport(
            file_sha256=file_sha256,
            sessions_added=sessions_added,
            books_matched=books_matched,
            books_unmatched=books_unmatched,
        )
    )

    return KoreaderConfirmResult(
        import_id="",
        sessions_added=sessions_added,
        sessions_skipped=max(0, total_sessions - sessions_added),
        books_matched=books_matched,
        books_unmatched=books_unmatched,
    )


@router.get("/unmatched", response_model=list[KoreaderBookPreview])
def unmatched_books(
    import_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
) -> list[KoreaderBookPreview]:
    """Livres KOReader non rattachés du dernier import pending, avec leurs
    candidats — l'écran « Livres KOReader non rattachés » (§4.3) se ressource
    ici après un rafraîchissement."""
    files = sorted(
        config.KOREADER_PENDING_DIR.glob("*.sqlite3"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return []
    path = files[0]
    if import_id and (not _valid_import_id(import_id) or import_id != path.stem):
        raise HTTPException(
            status_code=404, detail="Import inconnu ou expiré (re-uploader le fichier)"
        )
    try:
        stats = parse_statistics(path)
    except KoreaderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previews = _build_book_previews(
        session, stats, config.SESSION_GAP_SEC, detect_duration_factor(stats.books, stats.rows)
    )
    return [p for p in previews if not p.matched]
