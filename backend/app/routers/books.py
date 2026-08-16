"""Router /api/v1/books — CRUD livre, statut, couverture, taxonomie (§5).

Règles métier appliquées ici :
- La Bibliothèque n'affiche jamais un wishlist (16/08/2026) : `GET /books`
  exclut `is_wishlist=1` par défaut, quel que soit le filtre `status`.
  `wishlist=true` retourne uniquement les livres souhaités ; la seule
  sortie de wishlist est `POST /books/{id}/acquire` (is_wishlist -> 0,
  status -> 'tbr', owned -> 1).
- Un livre wishlist (`is_wishlist=1`) est non possédé (`owned=0`) et son
  `status` est sans objet — forcé à 'tbr' (valeur valide de l'enum).
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
from sqlalchemy import exists, update
from sqlmodel import Session, func, select
from starlette.datastructures import UploadFile

from app import config
from app.db import get_session
from app.models import (
    Author,
    Book,
    BookAuthor,
    BookFormat,
    BookLabel,
    Label,
    ReadEntry,
    Series,
)
from app.schemas import (
    BOOK_TYPES,
    BookCreate,
    BookFormatIn,
    BookFormatOut,
    BookList,
    BookOut,
    BookUpdate,
    CoverPayload,
    StatusUpdate,
    TbrReorder,
)
from app.services.covers import CoverError, download_and_store, store_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/books", tags=["books"])

# Tri accepté : colonnes sûres (pas d'interpolation SQL).
_SORT_COLUMNS = {
    "title": Book.title,
    "created": Book.created_at,
    "rating": Book.rating,
    "tbr_rank": Book.tbr_rank,  # Pile à lire = sélection ordonnée (15/08)
}

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

def _book_out(
    session: Session,
    book: Book,
    authors: list[str] | None = None,
    tags: list[str] | None = None,
    genres: list[str] | None = None,
) -> BookOut:
    """Construit BookOut : taxonomie + formats + série résolus, URLs locales.

    La session est passée explicitement pour résoudre `formats` et
    `series_name` (des colonnes d'autres tables) au même instant que la
    taxonomie — le coût est le même N+1 assumé qu'auteurs/tags/genres.
    """
    out = BookOut.model_validate(book.model_dump())
    if authors is not None:
        out.authors = authors
    if tags is not None:
        out.tags = tags
    if genres is not None:
        out.genres = genres
    out.formats = _get_formats(session, book.id)
    out.series_name = _get_series_name(session, book)
    if book.cover_path:
        thumb_rel = str(Path(book.cover_path).with_name("thumb.jpg"))
        out.cover_url = f"/covers/{book.cover_path}"
        out.cover_thumb_url = f"/covers/{thumb_rel}"
    return out


def _apply_status_rules(book: Book, prev_status: str | None = None) -> None:
    """Cohérence des états dépendant du statut (décisions produit 15/08).

    - `wishlist` n'est plus un statut depuis le 16/08/2026 : un livre
      souhaité porte `is_wishlist=1`, et son `status` est alors SANS OBJET
      — forcé à 'tbr' (valeur valide de l'enum, jamais une valeur morte) et
      `owned` à 0 (un souhaité n'est pas possédé). La seule sortie de
      wishlist est `POST /books/{id}/acquire` ; une écriture qui tenterait
      de déplacer un wishlist entre statuts est neutralisée ici.
    - quitter la Pile à lire (`tbr` -> autre chose) libère `tbr_rank` — le
      rang n'a de sens que dans la liste ; `tbr_note` est conservée (texte
      saisi par l'utilisateur, jamais effacé implicitement).
    - cesser d'être `reading` libère `is_primary_reading` — le flag n'a de
      sens que pour un livre en cours, et l'index partiel unique
      `uq_book_primary_reading` l'exigerait de toute façon au retour.
    Sur création, `prev_status` est None : aucune transition n'existe.
    """
    if book.is_wishlist:
        book.status = "tbr"  # sans objet tant que wishlist
        book.owned = 0       # un souhaité n'est pas possédé
    if prev_status is not None and prev_status != book.status:
        if prev_status == "tbr" and book.status != "tbr":
            book.tbr_rank = None
        if prev_status == "reading" and book.status != "reading":
            book.is_primary_reading = 0
    if book.is_wishlist or book.status != "tbr":
        # règle dérivée : pas de rang hors de la PAL — et un wishlist n'est
        # jamais dans la PAL, même si son status (sans objet) vaut 'tbr'.
        book.tbr_rank = None


def _check_price_allowed(book: Book) -> None:
    """Un livre en wishlist ne porte jamais de prix payé ni de date d'achat
    (décision produit 15/08 : le prix y serait « constaté », pas « payé »).

    On REFUSE (422) plutôt que de vider silencieusement : effacer le prix
    réel d'un livre déjà lu est une décision qui appartient à l'utilisateur.
    """
    if book.is_wishlist and (
        book.price_paid is not None or book.purchased_at is not None
    ):
        raise HTTPException(
            status_code=422,
            detail="Un livre en wishlist ne porte ni price_paid ni purchased_at",
        )


def _get_formats(session: Session, book_id: int) -> list[BookFormatOut]:
    """Formats du livre, triés par type (ordre stable pour le front)."""
    rows = session.exec(
        select(BookFormat)
        .where(BookFormat.book_id == book_id)
        .order_by(BookFormat.format)
    ).all()
    return [BookFormatOut(type=r.format, owned=bool(r.owned)) for r in rows]


def _replace_formats(session: Session, book: Book, formats: list[BookFormatIn]) -> None:
    """Remplacement complet des formats (pattern authors/tags).

    `book.id` doit être connu (flush en création). La liste est déjà validée
    (types + pas de doublon) par le schéma. L'appelant commit.
    """
    for link in session.exec(
        select(BookFormat).where(BookFormat.book_id == book.id)
    ).all():
        session.delete(link)
    for fmt in formats:
        session.add(BookFormat(book_id=book.id, format=fmt.type, owned=int(fmt.owned)))


def _upsert_series(session: Session, name: str) -> Series | None:
    """Série par nom (table unique) ; une chaîne vide retire la série."""
    name = name.strip()
    if not name:
        return None
    series = session.exec(select(Series).where(Series.name == name)).first()
    if series is None:
        series = Series(name=name)
        session.add(series)
        session.flush()  # récupère series.id
    return series


def _get_series_name(session: Session, book: Book) -> str | None:
    if book.series_id is None:
        return None
    series = session.get(Series, book.series_id)
    return series.name if series is not None else None


def _set_primary_reading(session: Session, book: Book) -> None:
    """Désigne le livre principal : flag exclusif parmi les `reading`.

    Contrainte réelle au niveau base (index partiel unique
    `uq_book_primary_reading`) : il faut désactiver l'actuel AVANT de poser
    le nouveau, dans la même transaction — sinon l'UPDATE du nouveau
    déclencherait une IntegrityError.
    """
    if book.status != "reading":
        raise HTTPException(
            status_code=422,
            detail="is_primary_reading ne se désigne que sur un livre en cours (status=reading)",
        )
    session.exec(
        update(Book)
        .where(Book.is_primary_reading == 1, Book.id != book.id)
        .values(is_primary_reading=0)
    )
    book.is_primary_reading = 1


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
    wishlist: bool = Query(default=False),
    type: str | None = Query(default=None),
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

    Mode Bibliothèque (défaut) : n'inclut JAMAIS un livre wishlist
    (`is_wishlist = 0`), quel que soit le filtre `status` passé — un
    souhaité n'est pas un statut parmi d'autres, c'est une vue séparée
    (16/08/2026). `wishlist=true` retourne uniquement les livres souhaités
    ; dans ce mode, `status` n'a pas de sens et est ignoré.
    `type` filtre par type de livre (`livre|manga|comics|manhwa`).
    Autres filtres : `tag` (nom exact), `genre` (nom exact), `author`
    (nom exact), `owned` (0/1), `q` (sous-chaîne titre/sous-titre).
    `sort` : `title` | `created` (défaut, plus récent d'abord) | `rating`
    | `tbr_rank` (Pile à lire : ordre de la sélection, livres sans rang en
    fin de liste).
    """
    stmt = select(Book)

    if wishlist:
        stmt = stmt.where(Book.is_wishlist == 1)
        # `status` est sans objet pour un wishlist : ignoré dans ce mode.
    else:
        # La Bibliothèque n'inclut JAMAIS un livre souhaité. `status !=
        # 'wishlist'` est un filet défensif : `wishlist` n'est plus une
        # valeur valide depuis le 16/08/2026, mais une ligne non migrée ne
        # doit pas fuiter dans la Bibliothèque ni matcher un filtre mort.
        stmt = stmt.where(Book.is_wishlist == 0, Book.status != "wishlist")
        if status:
            stmt = stmt.where(Book.status == status)
    if type is not None:
        if type not in BOOK_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"type invalide : {type!r} (livre|manga|comics|manhwa)",
            )
        stmt = stmt.where(Book.type == type)
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
    if sort == "tbr_rank":
        # NULLS en dernier : les livres de la PAL non encore rangés ne
        # passent pas devant les rangs 1..n (SQLite trie NULL en premier
        # en ASC — `is_(None)` renverse la priorité).
        stmt = stmt.order_by(Book.tbr_rank.is_(None), Book.tbr_rank.asc())
    elif sort == "created":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    books = session.exec(stmt).all()

    items = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        items.append(_book_out(session, b, _get_author_names(session, b.id), tags, genres))

    return BookList(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=BookOut, status_code=201)
async def create_book(
    payload: BookCreate,
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BookOut:
    """Crée un livre — depuis lookup (métadonnées + couverture) ou manuel.

    `is_wishlist=1` ajoute directement le livre à la wishlist (son `status`
    devient sans objet, forcé à 'tbr') ; `type` vaut 'livre' par défaut.
    Tout se joue dans une seule transaction : si le téléchargement de la
    couverture échoue, rien n'est persisté (pas de livre orphelin).
    """
    data = payload.model_dump(
        exclude={"authors", "tags", "genres", "cover_url", "formats", "series", "is_primary_reading"}
    )
    book = Book(**data)
    _apply_status_rules(book)
    _recompute_percent(book)
    _check_price_allowed(book)
    if payload.series is not None:
        series = _upsert_series(session, payload.series)
        if series is not None:
            book.series_id = series.id
    session.add(book)
    session.flush()  # récupère book.id pour le stockage des couvertures

    if payload.authors:
        _replace_authors(session, book, payload.authors)
    if payload.tags or payload.genres:
        _replace_labels(session, book, payload.tags, payload.genres)
    if payload.formats:
        _replace_formats(session, book, payload.formats)
    if payload.is_primary_reading:
        _set_primary_reading(session, book)

    try:
        if payload.cover_url:
            await _set_cover_from_url(session, book, payload.cover_url, payload.cover_source, client)
    except CoverError as exc:
        raise HTTPException(status_code=422, detail=f"couverture : {exc}") from exc

    session.commit()
    session.refresh(book)
    tags, genres = _get_labels(session, book.id)
    return _book_out(session, book, _get_author_names(session, book.id), tags, genres)


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, session: Session = Depends(get_session)) -> BookOut:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")
    tags, genres = _get_labels(session, book.id)
    return _book_out(session, book, _get_author_names(session, book.id), tags, genres)


@router.patch("/{book_id}", response_model=BookOut)
async def update_book(
    book_id: int,
    payload: BookUpdate,
    client: httpx.AsyncClient = Depends(get_http_client),
    session: Session = Depends(get_session),
) -> BookOut:
    """Mise à jour partielle. `authors`, `tags`, `genres`, `formats`
    remplacent leur liste ; `cover_url` déclenche un nouveau téléchargement
    local ; `series` upserté par nom (chaîne vide = retirer la série) ;
    `is_primary_reading=true` désigne le livre principal et déset l'actuel ;
    `type` (livre|manga|comics|manhwa) et `status` se posent directement.
    `is_wishlist` n'est PAS accepté ici : la seule sortie de wishlist est
    `POST /books/{id}/acquire` (et la création accepte l'entrée directe)."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    data = payload.model_dump(
        exclude_unset=True,
        exclude={"authors", "tags", "genres", "cover_url", "formats", "series", "is_primary_reading"},
    )
    prev_status = book.status  # avant application du payload : règles de transition
    for field, value in data.items():
        setattr(book, field, value)

    _apply_status_rules(book, prev_status)
    _recompute_percent(book)
    _check_price_allowed(book)

    if payload.series is not None:
        series = _upsert_series(session, payload.series)
        book.series_id = series.id if series is not None else None
        if series is None:
            book.series_index = None  # sans série, pas de numéro de tome
    if payload.formats is not None:
        _replace_formats(session, book, payload.formats)
    if payload.is_primary_reading is not None:
        if payload.is_primary_reading:
            _set_primary_reading(session, book)
        else:
            book.is_primary_reading = 0

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
    return _book_out(session, book, _get_author_names(session, book.id), tags, genres)


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


@router.post("/tbr/reorder", response_model=BookList)
def reorder_tbr(
    payload: TbrReorder,
    session: Session = Depends(get_session),
) -> BookList:
    """Réordonne la Pile à lire (décision produit 15/08 : sélection curatée).

    `payload.book_ids` définit l'ordre COMPLET voulu (1 = prochain lu) et
    la renumérotation se fait en une transaction : tous les `tbr` perdent
    leur rang, puis les livres listés reçoivent 1..n. Les livres encore
    `tbr` non listés restent donc en fin de liste (rang NULL).

    Strict par design : un id inexistant, non-`tbr`, wishlist ou dupliqué
    renvoie 422 AVANT toute modification — une liste périmée doit être
    rechargée par le front, pas corrigée ici (une session timer ouverte
    entre le chargement et le drag fait sortir un livre de la PAL).
    """
    # Déclarée avant `POST /{book_id}/status` : sinon Starlette matcherait
    # « tbr » contre `book_id` et répondrait 422 au lieu d'appeler ici.

    books_by_id: dict[int, Book] = {}
    for book_id in payload.book_ids:
        book = session.get(Book, book_id)
        if book is None:
            raise HTTPException(
                status_code=422, detail=f"Livre {book_id} introuvable"
            )
        # Un wishlist a un status sans objet (forcé à 'tbr') : il n'est
        # PAS dans la Pile à lire, rejeté comme un non-tbr (16/08/2026).
        if book.status != "tbr" or book.is_wishlist:
            raise HTTPException(
                status_code=422,
                detail=f"Le livre {book_id} n'est pas dans la Pile à lire (status={book.status})",
            )
        books_by_id[book_id] = book

    # La liste fournie EST la sélection : dérangement global puis renumérotation.
    session.exec(
        update(Book)
        .where(Book.status == "tbr", Book.is_wishlist == 0)
        .values(tbr_rank=None)
    )
    for rank, book_id in enumerate(payload.book_ids, start=1):
        books_by_id[book_id].tbr_rank = rank

    session.commit()

    # Réponse : la PAL dans son nouvel ordre (rangés d'abord, sans rang en
    # fin), prête à remplacer la liste du front sans round-trip.
    books = session.exec(
        select(Book)
        .where(Book.status == "tbr", Book.is_wishlist == 0)
        .order_by(Book.tbr_rank.is_(None), Book.tbr_rank.asc())
    ).all()
    items = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        items.append(_book_out(session, b, _get_author_names(session, b.id), tags, genres))
    return BookList(items=items, total=len(items), page=1, page_size=len(items))


@router.post("/{book_id}/status", response_model=BookOut)
def set_status(
    book_id: int,
    payload: StatusUpdate,
    session: Session = Depends(get_session),
) -> BookOut:
    """Déplacement rapide entre statuts (§5).

    `status=read` avec `finished_at` crée une `read_entry` (la date de fin
    appartient à la lecture). `wishlist` n'est plus une valeur acceptée
    (16/08/2026) : la validation du schéma la refuse (422). Un livre en
    wishlist n'a pas de statut de lecture significatif — toute écriture de
    statut est neutralisée à 'tbr' par `_apply_status_rules` ; la seule
    transition wishlist -> bibliothèque est `POST /books/{id}/acquire`.
    C'est le chemin MANUEL de la transition `tbr` -> `reading` (les deux
    chemins automatiques sont le timer et l'import KOReader, cf.
    sessions.mark_started_reading).
    """
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    prev_status = book.status
    book.status = payload.status
    _apply_status_rules(book, prev_status)
    _check_price_allowed(book)
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
    return _book_out(session, book, _get_author_names(session, book.id), tags, genres)


@router.post("/{book_id}/acquire", response_model=BookOut)
def acquire_book(book_id: int, session: Session = Depends(get_session)) -> BookOut:
    """Sortie de wishlist (16/08/2026) : « je l'ai acheté, il rejoint ma pile ».

    `is_wishlist` passe à 0, `status` à 'tbr', `owned` à 1. C'est la SEULE
    transition wishlist -> bibliothèque : il n'existe aucun endpoint pour
    rentrer un livre déjà en bibliothèque dans la wishlist (cas non
    demandé, cf. anti scope-creep). Sans body — rien à saisir.
    """
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")
    if book.is_wishlist != 1:
        raise HTTPException(
            status_code=422,
            detail="Ce livre n'est pas en wishlist — acquire ne concerne que les wishlist",
        )

    book.is_wishlist = 0
    book.status = "tbr"
    book.owned = 1
    session.add(book)
    session.commit()
    session.refresh(book)
    tags, genres = _get_labels(session, book.id)
    return _book_out(session, book, _get_author_names(session, book.id), tags, genres)


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
        return _book_out(session, book, _get_author_names(session, book.id), tags, genres)

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
        return _book_out(session, book, _get_author_names(session, book.id), tags, genres)

    raise HTTPException(
        status_code=415,
        detail="content-type non supporté (application/json ou multipart/form-data)",
    )
