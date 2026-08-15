"""Router /api/v1 — taxonomie : auteurs, séries et labels (tags/genres) (§5).

Ces endpoints alimentent les filtres et les vues de la Bibliothèque :
- `GET /authors` — tous les auteurs avec le nombre de livres liés.
- `GET /authors/{id}/books` — les livres d'un auteur.
- `GET /labels?kind=genre|tag` — labels d'un kind avec nombre de livres.
- `GET /series` — toutes les séries avec le nombre de livres liés
  (filtre « Série » de la Bibliothèque, décision produit 15/08).
- `GET /series/{id}/books` — les livres d'une série.

Le `book_count` est un compte *actuel* (livres liés), sans notion de
statut : la Bibliothèque (owned=1) se filtre côté `GET /books`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.models import Author, Book, BookAuthor, BookLabel, Label, Series
from app.schemas import (
    AuthorBooks,
    AuthorOut,
    BookOut,
    LabelList,
    LabelOut,
    SeriesBooks,
    SeriesOut,
)

from app.routers.books import _book_out, _get_author_names, _get_labels

router = APIRouter(tags=["taxonomie"])


@router.get("/authors", response_model=list[AuthorOut])
def list_authors(session: Session = Depends(get_session)) -> list[AuthorOut]:
    """Tous les auteurs, triés par nom, avec leur nombre de livres."""
    rows = session.exec(
        select(Author, func.count(BookAuthor.book_id))
        .outerjoin(BookAuthor, BookAuthor.author_id == Author.id)
        .group_by(Author.id)
        .order_by(Author.name)
    ).all()
    return [
        AuthorOut(
            id=author.id,
            name=author.name,
            openlibrary_key=author.openlibrary_key,
            book_count=count,
        )
        for author, count in rows
    ]


@router.get("/authors/{author_id}/books", response_model=AuthorBooks)
def author_books(
    author_id: int, session: Session = Depends(get_session)
) -> AuthorBooks:
    """Les livres d'un auteur (tous statuts confondus), plus récents d'abord."""
    author = session.get(Author, author_id)
    if author is None:
        raise HTTPException(status_code=404, detail="Auteur introuvable")

    count = session.exec(
        select(func.count(BookAuthor.book_id)).where(BookAuthor.author_id == author_id)
    ).one()

    books = session.exec(
        select(Book)
        .join(BookAuthor, BookAuthor.book_id == Book.id)
        .where(BookAuthor.author_id == author_id)
        .order_by(Book.created_at.desc())
    ).all()

    items: list[BookOut] = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        items.append(_book_out(session, b, _get_author_names(session, b.id), tags, genres))

    return AuthorBooks(
        author=AuthorOut(
            id=author.id,
            name=author.name,
            openlibrary_key=author.openlibrary_key,
            book_count=count,
        ),
        books=items,
    )


@router.get("/series", response_model=list[SeriesOut])
def list_series(session: Session = Depends(get_session)) -> list[SeriesOut]:
    """Toutes les séries, triées par nom, avec leur nombre de livres."""
    rows = session.exec(
        select(Series, func.count(Book.series_id))
        .outerjoin(Book, Book.series_id == Series.id)
        .group_by(Series.id)
        .order_by(Series.name)
    ).all()
    return [
        SeriesOut(id=series.id, name=series.name, book_count=count)
        for series, count in rows
    ]


@router.get("/series/{series_id}/books", response_model=SeriesBooks)
def series_books(
    series_id: int, session: Session = Depends(get_session)
) -> SeriesBooks:
    """Les livres d'une série, triés par numéro de tome (les livres sans
    tome en premier — SQLite trie NULL en tête en ASC)."""
    series = session.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail="Série introuvable")

    count = session.exec(
        select(func.count(Book.id)).where(Book.series_id == series_id)
    ).one()

    books = session.exec(
        select(Book)
        .where(Book.series_id == series_id)
        .order_by(Book.series_index.asc())
    ).all()

    items: list[BookOut] = []
    for b in books:
        tags, genres = _get_labels(session, b.id)
        items.append(_book_out(session, b, _get_author_names(session, b.id), tags, genres))

    return SeriesBooks(
        series=SeriesOut(id=series.id, name=series.name, book_count=count),
        books=items,
    )


@router.get("/labels", response_model=LabelList)
def list_labels(
    kind: str = Query(default="tag", pattern="^(genre|tag)$"),
    session: Session = Depends(get_session),
) -> LabelList:
    """Labels d'un kind (genre|tag), triés par nom, avec nombre de livres."""
    rows = session.exec(
        select(Label, func.count(BookLabel.book_id))
        .outerjoin(BookLabel, BookLabel.label_id == Label.id)
        .where(Label.kind == kind)
        .group_by(Label.id)
        .order_by(Label.name)
    ).all()

    items = [
        LabelOut(id=label.id, name=label.name, kind=label.kind, book_count=count)
        for label, count in rows
    ]
    return LabelList(items=items, total=len(items))
