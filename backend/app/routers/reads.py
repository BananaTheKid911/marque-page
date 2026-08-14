"""Router — lectures (read_entry, relectures) (§5, Phase 3).

Une `read_entry` représente une lecture complète d'un livre (une relecture
= une entrée supplémentaire). Contrairement aux sessions (durée+pages),
elle porte la temporalité longue (started_at/finished_at) et l'évaluation
(rating, review).

Règle métier : la note d'une lecture synchronise `book.rating` — la
`read_entry` la plus récente avec une note fait foi ; la suppression
recalcule depuis les entrées restantes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import Book, ReadEntry
from app.schemas import (
    ReadEntryCreate,
    ReadEntryList,
    ReadEntryOut,
    ReadEntryUpdate,
)

router = APIRouter(tags=["reads"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_out(r: ReadEntry) -> ReadEntryOut:
    return ReadEntryOut.model_validate(r.model_dump())


def _sync_book_rating(session: Session, book: Book) -> None:
    """Re-calcule book.rating depuis les read_entry notées.

    La lecture la plus récente (finished_at, sinon created_at) avec un
    rating non-null fait foi ; sans lecture notée, la note du livre est
    remise à None.
    """
    rated = session.exec(
        select(ReadEntry)
        .where(ReadEntry.book_id == book.id, ReadEntry.rating.is_not(None))
        .order_by(ReadEntry.finished_at.desc().nullslast(), ReadEntry.created_at.desc())
    ).all()
    book.rating = rated[0].rating if rated else None
    session.add(book)


@router.get("/books/{book_id}/reads", response_model=ReadEntryList)
def list_reads(book_id: int, session: Session = Depends(get_session)) -> ReadEntryList:
    """Lectures d'un livre, de la plus récente à la plus ancienne."""
    if session.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    rows = session.exec(
        select(ReadEntry)
        .where(ReadEntry.book_id == book_id)
        .order_by(ReadEntry.finished_at.desc().nullslast(), ReadEntry.created_at.desc())
    ).all()
    return ReadEntryList(items=[_read_out(r) for r in rows], total=len(rows))


@router.post("/books/{book_id}/reads", response_model=ReadEntryOut, status_code=201)
def create_read(
    book_id: int,
    payload: ReadEntryCreate,
    session: Session = Depends(get_session),
) -> ReadEntryOut:
    """Enregistre une lecture (relecture) d'un livre."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    read = ReadEntry(
        book_id=book_id,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        rating=payload.rating,
        review=payload.review,
        created_at=_now_iso(),
    )
    session.add(read)

    if payload.rating is not None:
        _sync_book_rating(session, book)

    session.commit()
    session.refresh(read)
    return _read_out(read)


@router.patch("/reads/{read_id}", response_model=ReadEntryOut)
def update_read(
    read_id: int,
    payload: ReadEntryUpdate,
    session: Session = Depends(get_session),
) -> ReadEntryOut:
    """Mise à jour partielle d'une lecture. Re-synchronise la note du livre
    si `rating` est fourni (ou si une note est retirée)."""
    read = session.get(ReadEntry, read_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Lecture introuvable")

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(read, field, value)
    session.add(read)

    book = session.get(Book, read.book_id)
    if book is not None:
        _sync_book_rating(session, book)

    session.commit()
    session.refresh(read)
    return _read_out(read)


@router.delete("/reads/{read_id}", status_code=204)
def delete_read(read_id: int, session: Session = Depends(get_session)) -> None:
    read = session.get(ReadEntry, read_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Lecture introuvable")

    book_id = read.book_id
    session.delete(read)

    book = session.get(Book, book_id)
    if book is not None:
        _sync_book_rating(session, book)
    session.commit()
