"""Router /api/v1/books — CRUD livre, statut, couverture, taxonomie (§5).

Règles métier appliquées ici :
- `wishlist` force `owned = 0` ; tout autre statut force `owned = 1`
  (SPEC.md §2 : la Bibliothèque = tous les livres `owned = 1`).
- `current_percent` est recalculé à chaque écriture touchant
  `current_page` et/ou `page_count` (`end_page / page_count`).
- Les auteurs, tags et genres sont upsertés par nom (tables `author` et
  `label` uniques) puis liés via les tables m2m. `PATCH authors|tags|genres`
  remplace la liste complète (une liste vide vide la liaison).
- `POST /books/{id}/status` avec `status=read` + `finished_at` crée une
  `read_entry` (§5) — la date de fin appartient à la lecture, pas au livre.
- Toute sélection de couverture (URL de variante ou upload manuel) est
  téléchargée/stockée **localement** : jamais de hotlink.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import exists
from sqlmodel import Session, func, select
from starlette.datastructures import UploadFile

from app import config
from app.db import get_session
from app.models import Author, Book, BookAuthor, BookLabel, Label, ReadEntry
from app.schemas import (
    BookCreate,
    BookList,
    BookOut,
    BookUpdate,
    CoverPayload,
    StatusUpdate,
)
from app.services.covers import CoverError, download_and_store, store_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])

# Tri accepté : colonnes sûres (pas d'interpolation SQL).
_SORT_COLUMNS = {"title": Book.title, "created": Book.created_at, "rating": Book.rating}

# Client HTTP singleton pour le téléchargement des couvertures — fermé dans
# le lifespan de main.py. Un client par requête serait jetable et sans gain.
_http_client = httpx.AsyncClient(
    timeout=config.HTTP_TIMEOUT_SEC,
    headers={"User-Agent": config.HTTP_USER_AGENT},
)


def get_http_client() -> httpx.AsyncClient:
    return _http_client


async def close_http_client() -> None:
    await _http_client.aclose()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _book_out(book: Book, authors: list[str] | None = None,
              tags: list[str] | None = None, genres: list[str] | None = None) -> BookOut:
    """Construit BookOut : taxonomie résolue + URLs de couverture locales."""
    out = BookOut.model_validate(book.model_dump())
    if authors is not None:
        out.authors = authors
    if tags is not None:
        out.tags = tags
    if genres is not None:
        out.genres = genres
    if book.cover_path:
        thumb_rel = str(Path(book.cover_path).with_name("thumb.jpg"))
        out.cover_url = f"/covers/{book.cover_path}"
        out.cover_thumb_url = f"/covers/{thumb_rel}"
    return out


def _apply_status_rules(book: Book, prev_status: str | None = None) -> None:
    """§2 : wishlist => non possédé ; tout autre statut => possédé.

    Cohérence des états dépendant du statut (décisions produit 15/08) :
    - quitter la Pile à lire (`tbr` -> autre chose) libère `tbr_rank` — le
      rang n'a de sens que dans la liste ; `tbr_note` est conservée (texte
      saisi par l'utilisateur, jamais effacé implicitement).
    - cesser d'être `reading` libère `is_primary_reading` — le flag n'a de
      sens que pour un livre en cours, et l'index partiel unique
      `uq_book_primary_reading` l'exigerait de toute façon au retour.
    Sur création, `prev_status` est None : aucune transition n'existe.
    """
    book.owned = 0 if book.status == "wishlist" else 1
    if prev_status is not None and prev_status != book.status:
        if prev_status == "tbr" and book.status != "tbr":
            book.tbr_rank = None
        if prev_status == "reading" and book.status != "reading":
            book.is_primary_reading = 0


def _recompute_percent(book: Book) -> None:
    """current_percent = current_page / page_count quand page_count > 0."""
    if book.page_count and book.page_count > 0:
        book.current_percent = round(book.current_page / book.page_count, 4)


def _get_author_names(session: Session, book_id: int) -> list[str]:
    rows = session.exec(
        select(Author.name)
        .join(BookAuthor, BookAuthor.author_id == Author.id)
        .where(BookAuthor.book_id == book_id)
        .order_by(Author.name)
    ).all()
    return list(rows)


def _get_labels(session: Session, book_id: int) -> tuple[list[str], list[str]]:
    """(tags, genres) d'un livre, ordre stable par nom."""
    rows = session.exec(
        select(Label.name, Label.kind)
        .join(BookLabel, BookLabel.label_id == Label.id)
        .where(BookLabel.book_id == book_id)
        .order_by(Label.name)
    ).all()
    tags = [name for name, kind in rows if kind == "tag"]
    genres = [name for name, kind in rows if kind == "genre"]
    return tags, genres


def _replace_authors(session: Session, book: Book, names: list[str]) -> None:
    """Upsert des auteurs par nom + remplacement des liaisons du livre."""
    for link in session.exec(select(BookAuthor).where(BookAuthor.book_id == book.id)).all():
        session.delete(link)

    for name in names:
        name = name.strip()
        if not name:
            continue
        author = session.exec(select(Author).where(Author.name == name)).first()
        if author is None:
            author = Author(name=name)
            session.add(author)
            session.flush()  # récupère author.id
        session.add(BookAuthor(book_id=book.id, author_id=author.id))


def _replace_labels(
    session: Session, book: Book, tags: list[str] | None, genres: list[str] | None
) -> None:
    """Remplace les liaisons label du livre, kind par kind.

    `tags`/`genres` à `None` = ne pas toucher ce kind ; liste = remplacement
    complet de ce kind (vide => liaisons du kind supprimées). Upsert dans
    `label` (unique sur name+kind).
    """

    def _replace_one(names: list[str] | None, kind: str) -> None:
        if names is None:
            return  # kind non fourni : inchangé
        # Purge uniquement les liaisons de ce kind.
        stale = session.exec(
            select(BookLabel)
            .join(Label, Label.id == BookLabel.label_id)
            .where(BookLabel.book_id == book.id, Label.kind == kind)
        ).all()
        for link in stale:
            session.delete(link)

        for name in names:
            name = name.strip()
            if not name:
                continue
            label = session.exec(
                select(Label).where(Label.name == name, Label.kind == kind)
            ).first()
            if label is None:
                label = Label(name=name, kind=kind)
                session.add(label)
                session.flush()
            session.add(BookLabel(book_id=book.id, label_id=label.id))

    _replace_one(tags, "tag")
    _replace_one(genres, "genre")


async def _set_cover_from_url(
    session: Session, book: Book, url: str, source: str | None, client: httpx.AsyncClient
) -> None:
    """Télécharge une variante choisie et l'enregistre localement.

    `book.id` doit déjà être connu (flush). Lève `CoverError` : l'appelant
    n'a qu'à ne pas committer pour que tout reparte (rollback).
    """
    rel = await download_and_store(url, book.id, client)
    book.cover_path = rel
    book.cover_source = source or "openlibrary"
    session.add(book)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=BookList)
def list_books(
    status: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    genre: str | None = Query(default=None),
    author: str | None = Query(default=None),
    owned: int | None = Query(default=None, ge=0, le=1),
    q: str | None = Query(default=None, max_length=200),
    sort: str = Query(default="created"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
) -> BookList:
    """Liste des livres avec filtres, tri et pagination (§5).

    Filtres : `status`, `tag` (nom exact), `genre` (nom exact), `author`
    (nom exact), `owned` (0/1), `q` (sous-chaîne titre/sous-titre).
    `sort` : `title` | `created` (défaut, plus récent d'abord) | `rating`.
    """
    stmt = select(Book)

    if status:
        stmt = stmt.where(Book.status == status)
    if owned is not None:
        stmt = stmt.where(Book.owned == owned)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Book.title.ilike(like) | Book.subtitle.ilike(like))

    if tag:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(BookLabel)
                .join(Label, Label.id == BookLabel.label_id)
                .where(BookLabel.book_id == Book.id, Label.kind == "tag", Label.name == tag)
            )
        )
    if genre:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(BookLabel)
                .join(Label, Label.id == BookLabel.label_id)
                .where(BookLabel.book_id == Book.id, Label.kind == "genre", Label.name == genre)
            )
        )
    if author:
        stmt = stmt.where(
            exists(
                select(1)
                .select_from(BookAuthor)
                .join(Author, Author.id == BookAuthor.author_id)
                .where(BookAuthor.book_id == Book.id, Author.name == author)
            )
        )

    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()

    sort_col = _SORT_COLUMNS.get(sort, Book.created_at)
    if sort == "created":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    books = session.exec(stmt).all()

    items = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        items.append(_book_out(b, _get_author_names(session, b.id), tags, genres))

    return BookList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=BookOut, status_code=201)
async def create_book(
    payload: BookCreate,
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BookOut:
    """Crée un livre — depuis lookup (métadonnées + couverture) ou manuel.

    Tout se joue dans une seule transaction : si le téléchargement de la
    couverture échoue, rien n'est persisté (pas de livre orphelin).
    """
    data = payload.model_dump(
        exclude={"authors", "tags", "genres", "cover_url"}
    )
    book = Book(**data)
    _apply_status_rules(book)
    _recompute_percent(book)
    session.add(book)
    session.flush()  # récupère book.id pour le stockage des couvertures

    if payload.authors:
        _replace_authors(session, book, payload.authors)
    if payload.tags or payload.genres:
        _replace_labels(session, book, payload.tags, payload.genres)

    try:
        if payload.cover_url:
            await _set_cover_from_url(session, book, payload.cover_url, payload.cover_source, client)
    except CoverError as exc:
        raise HTTPException(status_code=422, detail=f"couverture : {exc}") from exc

    session.commit()
    session.refresh(book)
    tags, genres = _get_labels(session, book.id)
    return _book_out(book, _get_author_names(session, book.id), tags, genres)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, session: Session = Depends(get_session)) -> BookOut:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")
    tags, genres = _get_labels(session, book.id)
    return _book_out(book, _get_author_names(session, book.id), tags, genres)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BookOut:
    """Mise à jour partielle. `authors`, `tags`, `genres` remplacent leur
    liste ; `cover_url` déclenche un nouveau téléchargement local."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    data = payload.model_dump(
        exclude_unset=True, exclude={"authors", "tags", "genres", "cover_url"}
    )
    prev_status = book.status  # avant application du payload : règles de transition
    for field, value in data.items():
        setattr(book, field, value)

    _apply_status_rules(book, prev_status)
    _recompute_percent(book)

    if payload.authors is not None:
        _replace_authors(session, book, payload.authors)
    if payload.tags is not None or payload.genres is not None:
        _replace_labels(session, book, payload.tags, payload.genres)

    try:
        if payload.cover_url is not None:
            await _set_cover_from_url(session, book, payload.cover_url, payload.cover_source, client)
    except CoverError as exc:
        raise HTTPException(status_code=422, detail=f"couverture : {exc}") from exc

    session.commit()
    session.refresh(book)
    tags, genres = _get_labels(session, book.id)
    return _book_out(book, _get_author_names(session, book.id), tags, genres)


@router.delete("/{book_id}", status_code=204)
def delete_book(book_id: int, session: Session = Depends(get_session)) -> None:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    session.delete(book)
    session.commit()

    # Nettoyage des fichiers de couverture locaux.
    book_dir = config.COVERS_DIR / str(book_id)
    try:
        if book_dir.exists():
            for f in book_dir.iterdir():
                f.unlink(missing_ok=True)
            book_dir.rmdir()
    except OSError:
        logger.warning("nettoyage couverture %s échoué", book_dir)


@router.post("/{book_id}/status", response_model=BookOut)
def set_status(
    book_id: int,
    payload: StatusUpdate,
    session: Session = Depends(get_session),
) -> BookOut:
    """Déplacement rapide entre statuts (§5).

    `status=read` avec `finished_at` crée une `read_entry` (la date de fin
    appartient à la lecture). `status=wishlist` force `owned=0` et
    inversement (§2). C'est le chemin MANUEL de la transition
    `tbr` -> `reading` (les deux chemins automatiques sont le timer et
    l'import KOReader, cf. sessions.mark_started_reading).
    """
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    prev_status = book.status
    book.status = payload.status
    _apply_status_rules(book, prev_status)
    session.add(book)

    if payload.status == "read":
        finished = payload.finished_at or date.today().isoformat()
        started = book.acquired_date or finished
        session.add(ReadEntry(
            book_id=book.id,
            started_at=started,
            finished_at=finished,
            created_at=_now_iso(),
        ))

    session.commit()
    session.refresh(book)
    tags, genres = _get_labels(session, book.id)
    return _book_out(book, _get_author_names(session, book.id), tags, genres)


@router.post("/{book_id}/cover", response_model=BookOut)
async def set_book_cover(
    book_id: int,
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BookOut:
    """Sélection de variante (JSON `{url, source}`) **ou** upload manuel
    (multipart `file`). L'image est toujours stockée localement.

    Le body est lu à la main : la présence d'un `UploadFile` optionnel dans
    la signature FastAPI contraindrait le content-type en multipart et
    casserait le mode JSON.
    """
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        try:
            raw = await request.json()
            payload = CoverPayload.model_validate(raw)
        except Exception as exc:  # JSON invalide ou schéma inconnu
            raise HTTPException(status_code=422, detail="body JSON invalide") from exc
        try:
            rel = await download_and_store(payload.url, book.id, client)
        except CoverError as exc:
            raise HTTPException(status_code=422, detail=f"couverture : {exc}") from exc
        book.cover_path = rel
        book.cover_source = payload.source
        session.add(book)
        session.commit()
        session.refresh(book)
        tags, genres = _get_labels(session, book.id)
        return _book_out(book, _get_author_names(session, book.id), tags, genres)

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not isinstance(upload, UploadFile):
            raise HTTPException(status_code=422, detail="champ `file` manquant")
        data = await upload.read()
        try:
            rel = store_image(data, book.id)
        except CoverError as exc:
            raise HTTPException(status_code=422, detail=f"couverture : {exc}") from exc
        book.cover_path = rel
        book.cover_source = "upload"
        session.add(book)
        session.commit()
        session.refresh(book)
        tags, genres = _get_labels(session, book.id)
        return _book_out(book, _get_author_names(session, book.id), tags, genres)

    raise HTTPException(
        status_code=415,
        detail="content-type non supporté (application/json ou multipart/form-data)",
    )
