"""Parser des statistiques KOReader (`statistics.sqlite3`) — SPEC §4.

Sécurité (règle non négociable) : le fichier uploadé est un *fichier
arbitraire fourni par l'utilisateur*. Il est toujours ouvert **en lecture
seule** (URI `mode=ro&immutable=1` — aucun journal, aucun verrou, aucune
écriture possible), et son contenu n'est **jamais interpolé** dans une
requête SQL de l'app : les requêtes vers ce fichier n'utilisent que des
paramètres liés ou des noms de colonnes issus de notre code, et les
valeurs extraites sont écrites dans la base app via SQLModel (paramétré).

Le schéma KOReader varie selon la version : on introspecte la table
présente (`page_stat_data` récente, `page_stat` ancienne) au lieu de la
supposer (SPEC §4.1). `book` est lue via `PRAGMA table_info` : toutes les
versions n'ont pas `authors` ni `md5`.
"""

from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


class KoreaderError(Exception):
    """Fichier illisible, non SQLite, ou schéma KOReader non reconnu."""


@dataclass
class KoreaderBook:
    """Un livre tel que KOReader le voit (table `book`)."""

    id: int
    title: str
    authors: str  # chaîne telle quelle (virgules ou « & »)
    md5: str | None
    total_read_time: int | None = None  # temps total de lecture (plugin stats)


@dataclass
class PageStatRow:
    """Une ligne de stats par page (une page lue = une ligne)."""

    id_book: int
    page: int | None
    start_time: float
    duration: float  # secondes (SPEC §4.2 : duration_sec = Σ duration)
    total_pages: int | None


@dataclass
class RebuiltSession:
    """Une session reconstruite (§4.2), prête à être écrite en base."""

    koreader_hash: str
    started_at: str  # ISO 8601 UTC
    ended_at: str
    duration_sec: int
    start_page: int | None
    end_page: int | None
    pages_read: int | None


@dataclass
class KoreaderStats:
    """Contenu extrait d'un statistics.sqlite3 (aucune écriture)."""

    books: list[KoreaderBook]
    rows: list[PageStatRow]


def session_hash(id_book: int, started_at_iso: str) -> str:
    """Idempotence (§4.2) : `sha256(id_book + started_at)`.

    Le séparateur `:` lève l'ambiguïté de concaténation (id_book=12 et 1)
    tout en restant fidèle à la règle : le hash ne dépend que du livre
    KOReader et du début de session, donc est stable entre deux imports
    du même fichier.
    """
    return hashlib.sha256(f"{id_book}:{started_at_iso}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# Lecture du fichier (lecture seule, paramétrée)
# ---------------------------------------------------------------------------

def _read_only_connect(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(path.resolve()), safe='/')}?mode=ro&immutable=1"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise KoreaderError("fichier KOReader illisible") from exc
    conn.row_factory = sqlite3.Row
    return conn


def parse_statistics(path: Path) -> KoreaderStats:
    """Extrait les livres et les lignes page-par-page du fichier.

    Lève `KoreaderError` si le fichier n'est pas une base SQLite ou ne
    ressemble pas à un statistics.sqlite3 KOReader.
    """
    conn = _read_only_connect(path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        stats_table = _pick_stats_table(tables)
        books = _read_books(conn)
        rows = _read_page_rows(conn, stats_table)
    except sqlite3.DatabaseError as exc:
        raise KoreaderError(
            "fichier invalide : pas une base SQLite lisible"
        ) from exc
    finally:
        conn.close()
    return KoreaderStats(books=books, rows=rows)


def _pick_stats_table(tables: set[str]) -> str:
    """SPÉC §4.1 : les anciennes versions utilisent `page_stat`."""
    if "page_stat_data" in tables:
        return "page_stat_data"
    if "page_stat" in tables:
        return "page_stat"
    raise KoreaderError(
        "schéma KOReader non reconnu (ni page_stat_data ni page_stat)"
    )


def _read_books(conn: sqlite3.Connection) -> list[KoreaderBook]:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(book)")}
    if "id" not in cols or "title" not in cols:
        raise KoreaderError("table book KOReader absente ou incomplète")

    # Colonnes optionnelles selon la version.
    select_cols = ["id", "title"]
    has_authors = "authors" in cols
    has_md5 = "md5" in cols
    has_total_time = "total_read_time" in cols
    if has_authors:
        select_cols.append("authors")
    if has_md5:
        select_cols.append("md5")
    if has_total_time:
        select_cols.append("total_read_time")

    books = []
    for row in conn.execute(f"SELECT {', '.join(select_cols)} FROM book"):
        books.append(
            KoreaderBook(
                id=int(row["id"]),
                title=str(row["title"] or ""),
                authors=str(row["authors"]) if has_authors and row["authors"] else "",
                md5=str(row["md5"]) if has_md5 and row["md5"] else None,
                total_read_time=(
                    int(row["total_read_time"])
                    if has_total_time and row["total_read_time"] is not None
                    else None
                ),
            )
        )
    return books


def _read_page_rows(conn: sqlite3.Connection, table: str) -> list[PageStatRow]:
    """Lit la table de stats par page (schéma identique dans les deux
    versions). `table` est une constante de notre code, jamais une valeur
    du fichier — pas d'injection possible.
    """
    rows = []
    for row in conn.execute(
        f"SELECT id_book, page, start_time, duration, total_pages FROM {table}"
    ):
        start_time = row["start_time"]
        if start_time is None:
            continue  # ligne sans horodatage : inexploitable
        rows.append(
            PageStatRow(
                id_book=int(row["id_book"]),
                page=int(row["page"]) if row["page"] is not None else None,
                start_time=float(start_time),
                duration=float(row["duration"] or 0),
                total_pages=(
                    int(row["total_pages"]) if row["total_pages"] is not None else None
                ),
            )
        )
    return rows


# ---------------------------------------------------------------------------
# Reconstruction des sessions (§4.2)
# ---------------------------------------------------------------------------

def detect_duration_factor(books: list[KoreaderBook], rows: list[PageStatRow]) -> float:
    """Auto-calibration de l'unité des durées (arbitrage Jordy, 15/08/2026).

    Les versions récentes de KOReader stockent `page_stat_data.duration` en
    **millisecondes**, les anciennes en secondes (hypothèse de la SPEC §4.2).
    Plutôt que de supposer, on compare `Σduration` par livre à
    `book.total_read_time` du plugin stats (référence) :

    - ratio ≈ 1    → mêmes unités → secondes supposées → facteur 1
    - ratio ≈ 1000 → duration en ms vs total en s → facteur 1/1000

    Le facteur majoritaire sur les livres exploitables gagne ; sans signal
    exploitable (pas de `total_read_time`, valeurs nulles), on garde les
    secondes — l'hypothèse de la SPEC.
    """
    near_ms = 0
    near_one = 0
    seen = 0
    for book in books:
        if not book.total_read_time or book.total_read_time <= 0:
            continue
        total_dur = sum(r.duration for r in rows if r.id_book == book.id)
        if total_dur <= 0:
            continue
        ratio = total_dur / book.total_read_time
        seen += 1
        if 500 <= ratio <= 2000:  # ≈ 1000
            near_ms += 1
        elif 0.5 <= ratio <= 2:  # ≈ 1
            near_one += 1
    if seen and near_ms >= max(1, seen // 2) and near_ms > near_one:
        return 0.001
    return 1.0


def sessions_by_book(
    rows: list[PageStatRow],
    gap_sec: int,
    duration_factor: float = 1.0,
) -> dict[int, list[RebuiltSession]]:
    """Sessions reconstruites, groupées par `id_book`.

    Algorithme §4.2 : lignes triées par `start_time`, découpage en sessions
    dès qu'un écart entre deux `start_time` consécutifs dépasse `gap_sec` ;
    par session, started_at = min(start_time), duration_sec = Σ durations,
    start/end_page = min/max page, pages_read = end - start + 1.

    `duration_factor` (1.0 ou 0.001) normalise l'unité des durées selon la
    calibration `detect_duration_factor` — les sessions stockent toujours
    des secondes (§2).
    """
    by_book: dict[int, list[PageStatRow]] = {}
    for row in rows:
        by_book.setdefault(row.id_book, []).append(row)

    result: dict[int, list[RebuiltSession]] = {}
    for book_id, book_rows in by_book.items():
        book_rows.sort(key=lambda r: (r.start_time, r.page or 0))
        result[book_id] = _rebuild(book_id, book_rows, gap_sec, duration_factor)
    return result


def _rebuild(
    id_book: int, rows: list[PageStatRow], gap_sec: int, duration_factor: float
) -> list[RebuiltSession]:
    sessions: list[RebuiltSession] = []
    current: list[PageStatRow] = [rows[0]]

    for previous, following in zip(rows, rows[1:]):
        if following.start_time - previous.start_time > gap_sec:
            sessions.append(_bundle(id_book, current, duration_factor))
            current = [following]
        else:
            current.append(following)
    sessions.append(_bundle(id_book, current, duration_factor))
    return sessions


def _bundle(id_book: int, rows: list[PageStatRow], duration_factor: float) -> RebuiltSession:
    started = datetime.fromtimestamp(rows[0].start_time, tz=timezone.utc)
    ended = datetime.fromtimestamp(rows[-1].start_time, tz=timezone.utc)
    started_at = started.isoformat()
    ended_at = ended.isoformat()

    pages = [r.page for r in rows if r.page is not None]
    start_page = min(pages) if pages else None
    end_page = max(pages) if pages else None
    pages_read = end_page - start_page + 1 if pages else None

    return RebuiltSession(
        koreader_hash=session_hash(id_book, started_at),
        started_at=started_at,
        ended_at=ended_at,
        duration_sec=round(sum(r.duration for r in rows) * duration_factor),
        start_page=start_page,
        end_page=end_page,
        pages_read=pages_read,
    )
