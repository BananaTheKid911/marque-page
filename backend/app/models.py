"""Modèles SQLModel — miroir exact du DDL de référence (SPEC.md §2).

Chaque classe correspond à une table du DDL, colonne pour colonne,
contraintes comprises (UNIQUE, FK ON DELETE CASCADE, index nommés,
server_default). Les timestamps sont stockés en TEXT ISO 8601 (UTC)
comme le prévoit le DDL.

Note : `sa_type=sa.Text()` force le type TEXT plutôt que le VARCHAR par
défaut d'AutoString, pour rester conforme à la lettre du DDL.
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, Numeric, Text, UniqueConstraint
# Importé sous un autre nom : le champ `text` de Highlight masquerait
# l'import au sein du corps de classe.
from sqlalchemy import text as sqltext
from sqlmodel import Field, SQLModel


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# LIVRES
# ---------------------------------------------------------------------------
class Book(SQLModel, table=True):
    __tablename__ = "book"
    __table_args__ = (
        Index("idx_book_status", "status"),
        Index("idx_book_koreader_md5", "koreader_md5"),
        # Type de livre (décision 16/08/2026) : enum borné au niveau base,
        # même pattern que le CHECK de `book_format.format`.
        CheckConstraint(
            "type IN ('livre', 'manga', 'comics', 'manhwa')",
            name="ck_book_type",
        ),
        # Dédup de l'import Book Track (§4.6) : deux livres ne peuvent pas
        # partager le même UUID Book Track. SQLite n'applique pas l'unicité
        # aux NULL — les livres hors import ne sont pas affectés.
        Index("uq_book_booktrack_id", "booktrack_id", unique=True),
        # Exclusivité du livre « en cours » : au plus un livre `reading`
        # porte `is_primary_reading = 1` à la fois (décision produit 15/08).
        Index(
            "uq_book_primary_reading",
            "is_primary_reading",
            unique=True,
            sqlite_where=sqltext("status = 'reading' AND is_primary_reading = 1"),
        ),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_type=Text)
    subtitle: str | None = Field(default=None, sa_type=Text)
    isbn10: str | None = Field(default=None, sa_type=Text)
    isbn13: str | None = Field(default=None, sa_type=Text)
    publisher: str | None = Field(default=None, sa_type=Text)
    published_date: str | None = Field(default=None, sa_type=Text)  # ISO ou année seule
    page_count: int | None = None
    language: str | None = Field(default=None, sa_type=Text)
    description: str | None = Field(default=None, sa_type=Text)
    cover_path: str | None = Field(default=None, sa_type=Text)  # chemin local, jamais de hotlink
    cover_source: str | None = Field(default=None, sa_type=Text)  # openlibrary | google | manual | upload
    status: str = Field(
        default="tbr",
        sa_type=Text,
        sa_column_kwargs={"server_default": sqltext("'tbr'")},
    )
    # tbr | reading | read | dnf | on_hold — `wishlist` n'est plus une valeur
    # de status depuis le 16/08/2026 : un livre souhaité porte `is_wishlist`.
    is_wishlist: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )  # 1 = souhaité, hors bibliothèque ; `status` sans objet tant que 1
    type: str = Field(
        default="livre",
        sa_type=Text,
        sa_column_kwargs={"server_default": sqltext("'livre'")},
    )
    # livre | manga | comics | manhwa (décision 16/08/2026) — CHECK ck_book_type
    owned: int = Field(
        default=1,
        sa_column_kwargs={"server_default": sqltext("1")},
    )  # 0 pour un wishlist ou un format non acheté (emprunt…)
    rating: float | None = None  # 0.5 .. 5.0 ; null si non noté
    current_page: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
    current_percent: float = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
    acquired_date: str | None = Field(default=None, sa_type=Text)
    # Série (décision produit 15/08) : `series_index` autorise les décimales
    # (1.5 pour un hors-série). NULL = le livre n'appartient à aucune série.
    # Typé Decimal : c'est ce que renvoie la colonne NUMERIC de SQLite (et
    # `model_dump()` d'un champ float serait incohérent avec la valeur).
    series_id: int | None = Field(
        default=None, foreign_key="series.id", ondelete="SET NULL"
    )
    series_index: Decimal | None = Field(default=None, sa_type=Numeric(5, 2))
    # Prix payé / date d'achat : un seul champ chacun, jamais remplis pour un
    # livre en wishlist (le prix y serait « constaté », pas « payé »).
    price_paid: float | None = None
    purchased_at: str | None = Field(default=None, sa_type=Text)
    # Livre « en cours » principal : flag exclusif parmi les livres `reading`
    # (contrainte au niveau base : index partiel unique ci-dessus). Désigné
    # manuellement, jamais automatiquement (décision produit 15/08).
    is_primary_reading: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
    # Pile à lire = sélection curatée distincte du filtre `status='tbr'` :
    # `tbr_rank` porte l'ordre (1 = prochain lu), `tbr_note` le motif
    # optionnel. Non renseignés hors de la Pile à lire.
    tbr_rank: int | None = None
    tbr_note: str | None = Field(default=None, sa_type=Text)
    # IDs externes pour ré-enrichissement
    openlibrary_work: str | None = Field(default=None, sa_type=Text)
    openlibrary_edition: str | None = Field(default=None, sa_type=Text)
    google_books_id: str | None = Field(default=None, sa_type=Text)
    koreader_md5: str | None = Field(default=None, sa_type=Text)  # clé de matching KOReader (partial md5)
    # UUID Book Track (import §4.6) : clé de dédup de l'import — jamais par
    # titre, un même titre peut exister en deux éditions/statuts.
    booktrack_id: str | None = Field(default=None, sa_type=Text)
    notes: str | None = Field(default=None, sa_type=Text)  # avis perso / review
    created_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)
    updated_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)


# ---------------------------------------------------------------------------
# SÉRIES
# ---------------------------------------------------------------------------
class Series(SQLModel, table=True):
    __tablename__ = "series"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, sa_type=Text)


# ---------------------------------------------------------------------------
# FORMATS × POSSESSION (décision produit 15/08)
# ---------------------------------------------------------------------------
class BookFormat(SQLModel, table=True):
    """Format d'un livre (physique | digital | audio), non exclusif, avec
    possession PAR format — un livre peut avoir le papier acheté et la
    version numérique simplement empruntée (d'où deux lignes : owned 1 et 0).

    Le champ `format` masque le builtin Python dans le corps de classe —
    accepté, comme `text` sur Highlight.
    """

    __tablename__ = "book_format"
    __table_args__ = (
        CheckConstraint(
            "format IN ('physique', 'digital', 'audio')",
            name="ck_book_format_type",
        ),
    )

    book_id: int = Field(
        default=None, primary_key=True, foreign_key="book.id", ondelete="CASCADE"
    )
    format: str = Field(default=None, primary_key=True, sa_type=Text)
    owned: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )  # 0 = consulté sans achat (emprunt…) ; 1 = possédé


# ---------------------------------------------------------------------------
# AUTEURS (m2m)
# ---------------------------------------------------------------------------
class Author(SQLModel, table=True):
    __tablename__ = "author"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, sa_type=Text)
    openlibrary_key: str | None = Field(default=None, sa_type=Text)


class BookAuthor(SQLModel, table=True):
    __tablename__ = "book_author"

    book_id: int = Field(
        default=None, primary_key=True, foreign_key="book.id", ondelete="CASCADE"
    )
    author_id: int = Field(
        default=None, primary_key=True, foreign_key="author.id", ondelete="CASCADE"
    )


# ---------------------------------------------------------------------------
# TAGS & GENRES unifiés (kind = genre|tag)
# ---------------------------------------------------------------------------
class Label(SQLModel, table=True):
    __tablename__ = "label"
    __table_args__ = (
        UniqueConstraint("name", "kind"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_type=Text)
    kind: str = Field(
        default="tag",
        sa_type=Text,
        sa_column_kwargs={"server_default": sqltext("'tag'")},
    )  # genre | tag


class BookLabel(SQLModel, table=True):
    __tablename__ = "book_label"

    book_id: int = Field(
        default=None, primary_key=True, foreign_key="book.id", ondelete="CASCADE"
    )
    label_id: int = Field(
        default=None, primary_key=True, foreign_key="label.id", ondelete="CASCADE"
    )


# ---------------------------------------------------------------------------
# LECTURES (supporte les relectures = plusieurs entrées par livre)
# ---------------------------------------------------------------------------
class ReadEntry(SQLModel, table=True):
    __tablename__ = "read_entry"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", ondelete="CASCADE")
    started_at: str | None = Field(default=None, sa_type=Text)  # date début de lecture
    finished_at: str | None = Field(default=None, sa_type=Text)  # date « livre lu »
    rating: float | None = None
    review: str | None = Field(default=None, sa_type=Text)
    created_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)


# ---------------------------------------------------------------------------
# SESSIONS DE LECTURE (cœur du besoin : durée + pages)
# ---------------------------------------------------------------------------
class ReadingSession(SQLModel, table=True):
    __tablename__ = "reading_session"
    __table_args__ = (
        Index("idx_session_book", "book_id"),
        Index("idx_session_started", "started_at"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", ondelete="CASCADE")
    started_at: str = Field(sa_type=Text)
    ended_at: str | None = Field(default=None, sa_type=Text)
    duration_sec: int  # saisi ou calculé
    start_page: int | None = None
    end_page: int | None = None
    pages_read: int | None = None  # end_page - start_page (ou saisi)
    note: str | None = Field(default=None, sa_type=Text)
    source: str = Field(
        default="manual",
        sa_type=Text,
        sa_column_kwargs={"server_default": sqltext("'manual'")},
    )  # manual | timer | koreader
    koreader_hash: str | None = Field(default=None, sa_type=Text)  # idempotence des imports KOReader
    created_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)


# ---------------------------------------------------------------------------
# HIGHLIGHTS / CITATIONS
# ---------------------------------------------------------------------------
class Highlight(SQLModel, table=True):
    __tablename__ = "highlight"
    __table_args__ = (
        Index("idx_highlight_book", "book_id"),
        {"sqlite_autoincrement": True},
    )

    id: int | None = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id", ondelete="CASCADE")
    text: str = Field(sa_type=Text)
    note: str | None = Field(default=None, sa_type=Text)
    page: int | None = None
    location: str | None = Field(default=None, sa_type=Text)  # xpointer/chapitre KOReader
    chapter: str | None = Field(default=None, sa_type=Text)
    color: str | None = Field(default=None, sa_type=Text)
    source: str = Field(
        default="manual",
        sa_type=Text,
        sa_column_kwargs={"server_default": sqltext("'manual'")},
    )  # manual | koreader
    highlighted_at: str | None = Field(default=None, sa_type=Text)
    created_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)


# ---------------------------------------------------------------------------
# JOURNAL DES IMPORTS KOReader (idempotence)
# ---------------------------------------------------------------------------
class KoreaderImport(SQLModel, table=True):
    __tablename__ = "koreader_import"
    __table_args__ = {"sqlite_autoincrement": True}

    id: int | None = Field(default=None, primary_key=True)
    file_sha256: str = Field(sa_type=Text)
    imported_at: str = Field(default_factory=_utcnow_iso, sa_type=Text)
    sessions_added: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
    books_matched: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
    books_unmatched: int = Field(
        default=0,
        sa_column_kwargs={"server_default": sqltext("0")},
    )
