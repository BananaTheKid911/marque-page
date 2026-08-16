"""Router — import Book Track (CSV) (§4.6, Phase 6).

`POST /import/booktrack` — migration initiale depuis un export de l'app
Book Track (`booktracker.csv`, 43 colonnes, format réel vérifié §4.6).

Flux :
1. Lecture du fichier (multipart `file`) + refus 422 AVANT toute
   modification si ce n'est pas un CSV Book Track valide (en-tête complet)
   ou si le fichier est vide.
2. Parsing RFC 4180 (`csv.DictReader`) → lignes normalisées + erreurs par
   ligne collectées (une ligne mal formée ne fait pas perdre les autres).
3. Insertion transactionnelle : dédup par `booktrack_id` (UUID Book Track,
   jamais par titre — un même titre peut exister en deux statuts), index
   unique `uq_book_booktrack_id` en filet. Tout échec d'insertion = rollback.
4. Couvertures téléchargées APRÈS le commit, en best-effort : un échec de
   téléchargement ne fait pas échouer l'import des données (même logique
   que `backup.py`). La règle « jamais de hotlink » reste : chaque URL est
   vérifiée contre `ALLOWED_COVER_HOSTS` avant téléchargement local.

Sémantique : AJOUT. Contrairement à `POST /import` (restauration = remplacement),
l'import Book Track ne supprime rien — c'est une migration initiale qui
remplit une base vide, et la dédup permet de le rejouer sans doublon.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app import config
from app.db import get_session
from app.models import Book, ReadEntry
from app.routers.books import (
    _replace_authors,
    _replace_formats,
    _replace_labels,
    _upsert_series,
    get_http_client,
)
from app.schemas import BookFormatIn, BooktrackImportResult
from app.services.booktrack import (
    BooktrackParseError,
    BooktrackRow,
    parse_booktrack_csv,
)
from app.services.covers import CoverError, download_and_store

router = APIRouter(prefix="/import/booktrack", tags=["booktrack"])

MAX_BOOKTRACK_BYTES = 10 * 1024 * 1024  # 10 Mo, un export réaliste est < 1 Mo


def _row_to_book(row: BooktrackRow) -> Book:
    """Construit le modèle `Book` depuis une ligne normalisée.

    Un livre souhaité (`is_wishlist=1`) ne porte jamais de prix ni de date
    d'achat (`_check_price_allowed` de books.py l'exigerait au commit) : on
    nettoie ici plutôt que de laisser échouer la ligne — un livre souhaité
    n'a pas de prix payé par définition.
    """
    return Book(
        title=row.title,
        subtitle=row.subtitle,
        isbn10=row.isbn10,
        isbn13=row.isbn13,
        publisher=row.publisher,
        published_date=row.published_date,
        page_count=row.page_count,
        language=row.language,
        description=row.description,
        status=row.status,
        is_wishlist=row.is_wishlist,
        owned=row.owned,
        rating=row.rating,
        purchased_at=row.purchased_at,
        price_paid=row.price_paid if not row.is_wishlist else None,
        series_index=row.series_index,
        cover_source=row.cover_source,
        booktrack_id=row.booktrack_id,
        created_at=row.read_started_at or None,
    )


@router.post("", response_model=BooktrackImportResult)
async def import_booktrack(
    file: UploadFile = File(...),
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BooktrackImportResult:
    """Importe un export Book Track CSV (migration initiale, ajout uniquement)."""
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=422,
            detail="le fichier doit être un CSV (export Book Track)",
        )

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=422, detail="fichier vide")
    if len(raw) > MAX_BOOKTRACK_BYTES:
        raise HTTPException(status_code=413, detail="fichier trop volumineux (max 10 Mo)")

    try:
        parsed = parse_booktrack_csv(raw)
    except BooktrackParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Dédup par UUID Book Track : les livres déjà importés (re-jeu du même
    # fichier, ou d'un export plus récent) ne sont pas recréés.
    # NB : `select(Book.booktrack_id)` est scalairisé par SQLModel — les rows
    # SONT les valeurs (des str), pas des tuples. `row[0]` serait le premier
    # caractère de l'UUID, un bug silencieux (aucun match, tout recréé).
    existing_ids = set(
        session.exec(
            select(Book.booktrack_id).where(Book.booktrack_id.is_not(None))
        ).all()
    )

    created: list[Book] = []
    skipped = 0
    for row in parsed.rows:
        if row.booktrack_id in existing_ids:
            skipped += 1
            continue
        book = _row_to_book(row)

        # Série par nom (même upsert qu'à la création par l'API).
        if row.series:
            series = _upsert_series(session, row.series)
            if series is not None:
                book.series_id = series.id

        session.add(book)
        try:
            session.flush()  # book.id connu pour les liaisons
        except IntegrityError:
            session.rollback()
            raise HTTPException(
                status_code=422,
                detail=f"Ligne {row.line_no} : violation d'intégrité (dédup booktrack_id ?)",
            ) from None

        if row.authors:
            _replace_authors(session, book, row.authors)
        if row.tags or row.genres:
            _replace_labels(session, book, row.tags, row.genres)
        if row.formats:
            _replace_formats(
                session,
                book,
                [BookFormatIn(type=f.type, owned=f.owned) for f in row.formats],
            )

        # Lecture associée : un livre `read` avec dates crée une read_entry
        # (started_at = début, finished_at = fin). Le `created_at` du livre
        # reflète la première lecture Book Track.
        if row.status == "read" and (row.read_started_at or row.read_finished_at):
            session.add(
                ReadEntry(
                    book_id=book.id,
                    started_at=row.read_started_at,
                    finished_at=row.read_finished_at,
                )
            )

        existing_ids.add(row.booktrack_id)
        created.append(book)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            status_code=422,
            detail="Échec d'insertion — rien n'a été modifié (données incohérentes ?)",
        ) from exc

    # Couvertures APRÈS le commit, best-effort : la base est importée même
    # si une image pose problème (URL morte, hôte non autorisé, hors format).
    covers_downloaded = 0
    covers_failed = 0
    for book in created:
        row = next((r for r in parsed.rows if r.booktrack_id == book.booktrack_id), None)
        if row is None or not row.cover_url:
            continue
        try:
            rel = await download_and_store(row.cover_url, book.id, client)
            book.cover_path = rel
            session.add(book)
            covers_downloaded += 1
        except CoverError:
            covers_failed += 1
    session.commit()

    return BooktrackImportResult(
        rows_parsed=len(parsed.rows),
        books_created=len(created),
        books_skipped=skipped,
        line_errors=parsed.errors,
        covers_downloaded=covers_downloaded,
        covers_failed=covers_failed,
    )
