"""Router — highlights / citations (§5, Phase 4).

Endpoints :
- `GET    /books/{book_id}/highlights`  — les citations d'un livre
- `POST   /books/{book_id}/highlights`  — création manuelle (`source=manual`)
- `GET    /highlights`                  — flux global + recherche plein texte
- `PATCH  /highlights/{id}`             — mise à jour partielle
- `DELETE /highlights/{id}`             — suppression

Recherche : la phase demande « retrouver par recherche » (critère
d'acceptation §8). Le DDL §2 ne prévoit pas de table FTS5, et l'échelle
est mono-utilisateur : la recherche est faite en `LIKE` sur `text` et
`note`, avec échappement des jokers. L'insensibilité casse **et** accents
est assurée par la fonction SQLite `unaccent` enregistrée dans db.py
(le LIKE natif de SQLite ne plie que l'ASCII). Un vrai index FTS5 (table
virtuelle + triggers de synchro) serait de la mécanique pour un gain nul
à ce volume — noté, pas implémenté.

Ordre : flux global et liste par livre triés par `highlighted_at`
(moins récent) puis `created_at` — « ce que j'ai surligné le plus
récemment d'abord », comme une liseuse.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from app.db import get_session, unaccent
from app.models import Book, Highlight
from app.schemas import HighlightCreate, HighlightList, HighlightOut, HighlightUpdate

router = APIRouter(tags=["highlights"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escape_like(term: str) -> str:
    """Échappe les jokers SQL LIKE (`%`, `_`) et le caractère d'échappement
    lui-même pour qu'une recherche de « 100% » reste littérale."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _feed_statement(book_id: int | None = None, q: str | None = None):
    """Requête de base du flux : Highlight + titre du livre joint.

    `book_id` filtre sur un livre, `q` cherche une sous-chaîne
    insensible à la casse dans `text` ou `note`.
    """
    stmt = select(Highlight, Book.title).join(Book, Book.id == Highlight.book_id)
    if book_id is not None:
        stmt = stmt.where(Highlight.book_id == book_id)
    if q:
        like = f"%{_escape_like(unaccent(q))}%"
        stmt = stmt.where(
            func.unaccent(Highlight.text).like(like, escape="\\")
            | func.unaccent(Highlight.note).like(like, escape="\\")
        )
    return stmt.order_by(
        Highlight.highlighted_at.desc().nullslast(), Highlight.created_at.desc()
    )


def _highlight_out(highlight: Highlight, book_title: str | None) -> HighlightOut:
    out = HighlightOut.model_validate(highlight.model_dump())
    out.book_title = book_title
    return out


def _fetch_book(session: Session, book_id: int) -> Book:
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")
    return book


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/highlights", response_model=HighlightList)
def list_highlights_feed(
    q: str | None = Query(default=None, max_length=200),
    book_id: int | None = Query(default=None, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    session: Session = Depends(get_session),
) -> HighlightList:
    """Flux global de citations, toutes sources confondues (§6.7).

    `q` recherche dans `text` et `note` (insensible à la casse) ;
    `book_id` restreint à un livre. Tri : `highlighted_at` récent d'abord.
    """
    stmt = _feed_statement(book_id=book_id, q=q)
    total = session.exec(select(func.count()).select_from(stmt.subquery())).one()
    rows = session.exec(stmt.offset((page - 1) * page_size).limit(page_size)).all()

    items = [_highlight_out(h, title) for h, title in rows]
    return HighlightList(items=items, total=total)


@router.get("/books/{book_id}/highlights", response_model=HighlightList)
def list_book_highlights(
    book_id: int,
    session: Session = Depends(get_session),
) -> HighlightList:
    """Citations d'un livre, plus récentes d'abord."""
    book = _fetch_book(session, book_id)
    rows = session.exec(_feed_statement(book_id=book_id)).all()
    items = [_highlight_out(h, book.title) for h, _title in rows]
    return HighlightList(items=items, total=len(items))


@router.post("/books/{book_id}/highlights", response_model=HighlightOut, status_code=201)
def create_highlight(
    book_id: int,
    payload: HighlightCreate,
    session: Session = Depends(get_session),
) -> HighlightOut:
    """Ajoute une citation à un livre. `source` est forcé à `manual` — seul
    l'import KOReader (Phase 5) écrira `source=koreader`."""
    book = _fetch_book(session, book_id)

    highlight = Highlight(
        book_id=book_id,
        text=payload.text,
        note=payload.note,
        page=payload.page,
        chapter=payload.chapter,
        color=payload.color,
        source="manual",
        highlighted_at=payload.highlighted_at,
        created_at=_now_iso(),
    )
    session.add(highlight)
    session.commit()
    session.refresh(highlight)
    return _highlight_out(highlight, book.title)


@router.patch("/highlights/{highlight_id}", response_model=HighlightOut)
def update_highlight(
    highlight_id: int,
    payload: HighlightUpdate,
    session: Session = Depends(get_session),
) -> HighlightOut:
    """Mise à jour partielle d'une citation."""
    highlight = session.get(Highlight, highlight_id)
    if highlight is None:
        raise HTTPException(status_code=404, detail="Highlight introuvable")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(highlight, field, value)
    session.add(highlight)
    session.commit()
    session.refresh(highlight)

    book = session.get(Book, highlight.book_id)
    return _highlight_out(highlight, book.title if book else None)


@router.delete("/highlights/{highlight_id}", status_code=204)
def delete_highlight(
    highlight_id: int,
    session: Session = Depends(get_session),
) -> None:
    highlight = session.get(Highlight, highlight_id)
    if highlight is None:
        raise HTTPException(status_code=404, detail="Highlight introuvable")

    session.delete(highlight)
    session.commit()
