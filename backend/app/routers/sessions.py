"""Router — sessions de lecture + timer in-app (§5, Phase 3).

Règles métier :
- Toute écriture de session re-synchronise la progression du livre :
  `current_page = max(end_page)` des sessions, `current_percent =
  current_page / page_count` (SPEC §2).
- Timer : `POST /timer/start` ouvre une session `source='timer'`
  (`ended_at` NULL, durée 0) ; `POST /timer/stop` la retrouve, calcule
  `duration_sec` depuis `started_at`, pose `end_page` et clôture.
  Le chrono vit aussi côté client : si le serveur a redémarré entre les
  deux appels, l'utilisateur perd la session ouverte (d'où le stockage
  client doublé, §6 « session live stockée côté client + serveur »).
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from app.db import get_session
from app.models import Book, ReadingSession
from app.schemas import (
    ReadingSessionCreate,
    ReadingSessionOut,
    ReadingSessionUpdate,
    SessionList,
    TimerStart,
    TimerStop,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sessions"])


# ---------------------------------------------------------------------------
# Helpers partagés (réutilisés par reads.py pour la cohérence)
# ---------------------------------------------------------------------------

def sync_book_progress(session: Session, book: Book) -> None:
    """Re-calcule `current_page`/`current_percent` depuis les sessions.

    `current_page` = page la plus loin atteinte (`max(end_page)`) ;
    `current_percent` = `current_page / page_count` quand page_count > 0.
    L'appelant commit.
    """
    max_end = session.exec(
        select(func.max(ReadingSession.end_page)).where(ReadingSession.book_id == book.id)
    ).one()
    book.current_page = max_end if max_end is not None else 0
    if book.page_count and book.page_count > 0:
        book.current_percent = round(book.current_page / book.page_count, 4)
    else:
        book.current_percent = 0
    session.add(book)


def mark_started_reading(book: Book) -> None:
    """Transition automatique `tbr` -> `reading` (décision produit 15/08).

    Un livre quitte la Pile à lire dès qu'une lecture réelle commence, par
    deux des trois chemins : session timer (`POST /timer/start`) et import
    KOReader apportant des sessions (§4.2). Le troisième chemin — l'action
    manuelle du front — passe par `POST /books/{id}/status`, géré dans
    books.py.

    Le rang est libéré (il n'a de sens que dans la liste) ; `tbr_note` est
    conservée : c'est un texte saisi par l'utilisateur, jamais effacé
    implicitement. La désignation du livre « en cours » principal reste
    manuelle (cette transition ne touche pas `is_primary_reading`), et
    `on_hold` n'est volontairement pas traité ici — seul le chemin manuel
    le reprend. L'appelant commit.
    """
    if book.status == "tbr":
        book.status = "reading"
        book.tbr_rank = None


def _session_out(s: ReadingSession) -> ReadingSessionOut:
    return ReadingSessionOut.model_validate(s.model_dump())


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Sessions (lecture)
# ---------------------------------------------------------------------------

@router.get("/books/{book_id}/sessions", response_model=SessionList)
def list_sessions(
    book_id: int, session: Session = Depends(get_session)
) -> SessionList:
    """Sessions d'un livre, de la plus récente à la plus ancienne."""
    if session.get(Book, book_id) is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    rows = session.exec(
        select(ReadingSession)
        .where(ReadingSession.book_id == book_id)
        .order_by(ReadingSession.started_at.desc())
    ).all()
    return SessionList(items=[_session_out(r) for r in rows], total=len(rows))


@router.post("/books/{book_id}/sessions", response_model=ReadingSessionOut, status_code=201)
def create_session(
    book_id: int,
    payload: ReadingSessionCreate,
    session: Session = Depends(get_session),
) -> ReadingSessionOut:
    """Saisie manuelle d'une session (§5). Re-synchronise la progression."""
    book = session.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    # pages_read dérivé si non fourni et les deux pages sont connues.
    pages_read = payload.pages_read
    if pages_read is None and payload.start_page is not None and payload.end_page is not None:
        pages_read = max(0, payload.end_page - payload.start_page)

    reading_session = ReadingSession(
        book_id=book_id,
        started_at=payload.started_at,
        ended_at=payload.ended_at,
        duration_sec=payload.duration_sec,
        start_page=payload.start_page,
        end_page=payload.end_page,
        pages_read=pages_read,
        note=payload.note,
        source="manual",
    )
    session.add(reading_session)
    sync_book_progress(session, book)
    session.commit()
    session.refresh(reading_session)
    return _session_out(reading_session)


@router.patch("/sessions/{session_id}", response_model=ReadingSessionOut)
def update_session(
    session_id: int,
    payload: ReadingSessionUpdate,
    session: Session = Depends(get_session),
) -> ReadingSessionOut:
    """Mise à jour partielle d'une session + re-synchronisation progression."""
    reading_session = session.get(ReadingSession, session_id)
    if reading_session is None:
        raise HTTPException(status_code=404, detail="Session introuvable")

    data = payload.model_dump(exclude_unset=True, exclude={"pages_read"})
    for field, value in data.items():
        setattr(reading_session, field, value)

    if payload.pages_read is not None:
        reading_session.pages_read = payload.pages_read
    elif (
        reading_session.start_page is not None and reading_session.end_page is not None
    ):
        reading_session.pages_read = max(
            0, reading_session.end_page - reading_session.start_page
        )

    session.add(reading_session)
    book = session.get(Book, reading_session.book_id)
    if book is not None:
        sync_book_progress(session, book)
    session.commit()
    session.refresh(reading_session)
    return _session_out(reading_session)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: int, session: Session = Depends(get_session)) -> None:
    reading_session = session.get(ReadingSession, session_id)
    if reading_session is None:
        raise HTTPException(status_code=404, detail="Session introuvable")

    book_id = reading_session.book_id
    session.delete(reading_session)

    book = session.get(Book, book_id)
    if book is not None:
        sync_book_progress(session, book)
    session.commit()


# ---------------------------------------------------------------------------
# Timer (session live)
# ---------------------------------------------------------------------------

@router.post("/timer/start", response_model=ReadingSessionOut, status_code=201)
def timer_start(
    payload: TimerStart,
    session: Session = Depends(get_session),
) -> ReadingSessionOut:
    """Ouvre une session timer (§5). Refuse si une session timer est déjà
    ouverte pour ce livre (pas de doublon de chrono)."""
    book = session.get(Book, payload.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    open_session = session.exec(
        select(ReadingSession).where(
            ReadingSession.book_id == payload.book_id,
            ReadingSession.source == "timer",
            ReadingSession.ended_at.is_(None),
        )
    ).first()
    if open_session is not None:
        raise HTTPException(
            status_code=409,
            detail="Une session timer est déjà en cours pour ce livre",
        )

    reading_session = ReadingSession(
        book_id=payload.book_id,
        started_at=datetime.now().astimezone().isoformat(),
        duration_sec=0,
        start_page=book.current_page or None,
        source="timer",
    )
    session.add(reading_session)
    # Chemin automatique n°1 vers `reading` (décision produit 15/08) :
    # démarrer une session in-app fait quitter la Pile à lire au livre.
    mark_started_reading(book)
    session.commit()
    session.refresh(reading_session)
    return _session_out(reading_session)


@router.post("/timer/stop", response_model=ReadingSessionOut)
def timer_stop(
    payload: TimerStop,
    session: Session = Depends(get_session),
) -> ReadingSessionOut:
    """Clôture la session timer ouverte du livre : calcule la durée depuis
    `started_at`, pose `end_page` et re-synchronise la progression."""
    book = session.get(Book, payload.book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Livre introuvable")

    open_session = session.exec(
        select(ReadingSession).where(
            ReadingSession.book_id == payload.book_id,
            ReadingSession.source == "timer",
            ReadingSession.ended_at.is_(None),
        )
    ).first()
    if open_session is None:
        raise HTTPException(
            status_code=409,
            detail="Aucune session timer en cours pour ce livre",
        )

    now = datetime.now().astimezone()
    started = _parse_iso(open_session.started_at)
    duration = max(0, int((now - started).total_seconds())) if started else 0

    open_session.ended_at = now.isoformat()
    open_session.duration_sec = duration
    open_session.end_page = payload.end_page
    if open_session.start_page is not None:
        open_session.pages_read = max(0, payload.end_page - open_session.start_page)

    session.add(open_session)
    sync_book_progress(session, book)
    session.commit()
    session.refresh(open_session)
    return _session_out(open_session)
