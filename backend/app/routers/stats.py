"""Router /api/v1/stats — dashboard & agrégations (§5, Phase 3).

Endpoints :
- `GET /stats/overview` — totaux : livres, temps, pages, streak, note moyenne.
- `GET /stats/timeline?range=day|week|month` — sessions agrégées par période.
- `GET /stats/by-genre` et `GET /stats/by-author` — répartition durée/pages.

Conventions :
- La "journée" est extraite des 10 premiers caractères de l'ISO (le fuseau
  du conteneur est Europe/Paris ; les saisies manuelles sont souvent des
  dates seules).
- `pages_read` NULL (session sans pages) compte comme 0.
- Le streak accorde une grâce d'un jour : si aucune session aujourd'hui
  mais une hier, le compteur démarre d'hier.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.db import get_session
from app.models import Author, Book, BookAuthor, BookLabel, Label, ReadingSession
from app.schemas import (
    BreakdownItem,
    StatsBreakdown,
    StatsOverview,
    StatsTimeline,
    TimelinePoint,
)

router = APIRouter(prefix="/stats", tags=["stats"])


def _day(iso: str) -> str:
    return iso[:10]


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@router.get("/overview", response_model=StatsOverview)
def stats_overview(session: Session = Depends(get_session)) -> StatsOverview:
    books = session.exec(select(Book)).all()
    sessions = session.exec(select(ReadingSession)).all()

    total_owned = sum(1 for b in books if b.owned == 1)
    # `wishlist` n'est plus un statut (16/08/2026) : la wishlist se compte
    # par `is_wishlist=1`, et la Pile à lire = tbr HORS wishlist (un livre
    # souhaité a un status sans objet, forcé à 'tbr', qui ne compte pas).
    books_read = sum(1 for b in books if b.status == "read")
    books_reading = sum(1 for b in books if b.status == "reading")
    books_tbr = sum(1 for b in books if b.status == "tbr" and b.is_wishlist == 0)
    books_wishlist = sum(1 for b in books if b.is_wishlist == 1)

    ratings = [b.rating for b in books if b.rating is not None]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    total_duration = sum(s.duration_sec or 0 for s in sessions)
    total_pages = sum(s.pages_read or 0 for s in sessions)

    return StatsOverview(
        total_books=len(books),
        books_owned=total_owned,
        books_read=books_read,
        books_reading=books_reading,
        books_tbr=books_tbr,
        books_wishlist=books_wishlist,
        total_sessions=len(sessions),
        total_duration_sec=total_duration,
        total_pages_read=total_pages,
        streak_days=_compute_streak(sessions),
        avg_rating=avg_rating,
    )


def _compute_streak(sessions: list[ReadingSession]) -> int:
    """Jours consécutifs avec ≥ 1 session, avec grâce d'un jour.

    Point de départ : aujourd'hui si une session y existe, sinon hier.
    """
    days = {_day(s.started_at) for s in sessions}
    if not days:
        return 0

    today = date.today()
    anchor = today
    if _day(today.isoformat()) not in days:
        anchor = today - timedelta(days=1)

    streak = 0
    cursor = anchor
    while _day(cursor.isoformat()) in days:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=StatsTimeline)
def stats_timeline(
    range: str = Query(default="day", pattern="^(day|week|month)$"),
    session: Session = Depends(get_session),
) -> StatsTimeline:
    sessions = session.exec(select(ReadingSession)).all()

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"duration_sec": 0, "pages_read": 0, "sessions": 0}
    )
    for s in sessions:
        period = _period_key(s.started_at, range)
        b = buckets[period]
        b["duration_sec"] += s.duration_sec or 0
        b["pages_read"] += s.pages_read or 0
        b["sessions"] += 1

    points = [
        TimelinePoint(period=p, **v)
        for p, v in sorted(buckets.items(), key=lambda kv: kv[0])
    ]
    return StatsTimeline(points=points)


def _period_key(iso: str, range: str) -> str:
    day = _day(iso)
    if range == "day":
        return day
    if range == "month":
        return day[:7]
    # semaine ISO : "2026-W33"
    d = date.fromisoformat(day)
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


# ---------------------------------------------------------------------------
# Répartition genre / auteur
# ---------------------------------------------------------------------------

@router.get("/by-genre", response_model=StatsBreakdown)
def stats_by_genre(session: Session = Depends(get_session)) -> StatsBreakdown:
    """Durée/pages/sessions regroupées par genre (label kind='genre')."""
    rows = session.exec(
        select(ReadingSession, Label.name)
        .join(Book, Book.id == ReadingSession.book_id)
        .join(BookLabel, BookLabel.book_id == Book.id)
        .join(Label, Label.id == BookLabel.label_id)
        .where(Label.kind == "genre")
    ).all()

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"duration_sec": 0, "pages_read": 0, "sessions": 0}
    )
    for s, genre in rows:
        b = buckets[genre]
        b["duration_sec"] += s.duration_sec or 0
        b["pages_read"] += s.pages_read or 0
        b["sessions"] += 1

    items = [
        BreakdownItem(label=g, **v)
        for g, v in sorted(buckets.items(), key=lambda kv: -kv[1]["duration_sec"])
    ]
    return StatsBreakdown(items=items)


@router.get("/by-author", response_model=StatsBreakdown)
def stats_by_author(session: Session = Depends(get_session)) -> StatsBreakdown:
    """Durée/pages/sessions regroupées par auteur."""
    rows = session.exec(
        select(ReadingSession, Author.name)
        .join(Book, Book.id == ReadingSession.book_id)
        .join(BookAuthor, BookAuthor.book_id == Book.id)
        .join(Author, Author.id == BookAuthor.author_id)
    ).all()

    buckets: dict[str, dict[str, int]] = defaultdict(
        lambda: {"duration_sec": 0, "pages_read": 0, "sessions": 0}
    )
    for s, author in rows:
        b = buckets[author]
        b["duration_sec"] += s.duration_sec or 0
        b["pages_read"] += s.pages_read or 0
        b["sessions"] += 1

    items = [
        BreakdownItem(label=a, **v)
        for a, v in sorted(buckets.items(), key=lambda kv: -kv[1]["duration_sec"])
    ]
    return StatsBreakdown(items=items)
