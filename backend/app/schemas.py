"""Schémas Pydantic de l'API Marque-page (préfixe /api/v1).

Ce fichier porte exclusivement les modèles de **requête/réponse HTTP** :
lookup (§3), couvertures, CRUD book (§5). Les modèles de persistance
vivent dans app.models (SQLModel, miroir du DDL §2).

Conventions :
- `Lookup*` = données externes agrégées (Open Library + Google Books).
- `Book*` = données de la base (le `Book` SQLModel n'est jamais exposé brut).
- Les URLs de couverture servies sont toujours locales (`/covers/...`).
"""

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# LOOKUP — données agrégées depuis Open Library / Google Books
# ---------------------------------------------------------------------------

#: Statuts de livre valides (SPEC.md §2).
BOOK_STATUSES = {"wishlist", "tbr", "reading", "read", "dnf", "on_hold"}


class CoverCandidate(BaseModel):
    """Une variante de couverture candidate (jamais hotlink : téléchargée
    localement au moment de la sélection, §3)."""

    url: str
    width: int | None = None
    height: int | None = None
    source: str  # openlibrary | google


class LookupMetadata(BaseModel):
    """Métadonnées normalisées, quelle que soit la source."""

    title: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None
    openlibrary_work: str | None = None
    openlibrary_edition: str | None = None
    google_books_id: str | None = None


class LookupResult(LookupMetadata):
    """Réponse de `GET /lookup?isbn=…` : métadonnées + variantes de couverture."""

    covers: list[CoverCandidate] = Field(default_factory=list)
    source: str  # openlibrary | google — source des métadonnées dominantes


class LookupCandidate(LookupMetadata):
    """Un candidat de `GET /lookup?q=…` (recherche titre → top 10).

    `cover_thumb` est un aperçu rapide issu du moteur de recherche ;
    les variantes complètes s'obtiennent via `GET /lookup/covers`.
    """

    cover_thumb: str | None = None
    source: str


# ---------------------------------------------------------------------------
# COUVERTURES — téléchargement local
# ---------------------------------------------------------------------------

class CoverPayload(BaseModel):
    """Sélection d'une variante : le backend télécharge l'image en local."""

    url: str
    source: str = "openlibrary"  # openlibrary | google | manual | upload


# ---------------------------------------------------------------------------
# BOOK — CRUD
# ---------------------------------------------------------------------------

class BookCreate(BaseModel):
    """Création d'un livre (depuis lookup ou manuel). Tous les champs sont
    optionnels sauf `title`. `cover_url` déclenche le téléchargement local.
    `tags` et `genres` sont des listes de noms, upsertées dans `label`."""

    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    language: str | None = None
    description: str | None = None
    status: str = "tbr"
    owned: int = 1
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    current_page: int = Field(default=0, ge=0)
    acquired_date: str | None = None
    openlibrary_work: str | None = None
    openlibrary_edition: str | None = None
    google_books_id: str | None = None
    koreader_md5: str | None = None
    notes: str | None = None
    cover_url: str | None = None  # variante choisie -> téléchargée localement
    cover_source: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in BOOK_STATUSES:
            raise ValueError(f"status invalide : {v!r}")
        return v

    @field_validator("owned")
    @classmethod
    def _check_owned(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("owned doit valoir 0 ou 1")
        return v


class BookUpdate(BaseModel):
    """Mise à jour partielle d'un livre. `authors`, `tags` et `genres`
    remplaçant la liste complète quand fournis (une liste vide les vide).
    `cover_url` déclenche un nouveau téléchargement local."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: list[str] | None = None
    tags: list[str] | None = None
    genres: list[str] | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    language: str | None = None
    description: str | None = None
    status: str | None = None
    owned: int | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    current_page: int | None = Field(default=None, ge=0)
    acquired_date: str | None = None
    openlibrary_work: str | None = None
    openlibrary_edition: str | None = None
    google_books_id: str | None = None
    koreader_md5: str | None = None
    notes: str | None = None
    cover_url: str | None = None
    cover_source: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in BOOK_STATUSES:
            raise ValueError(f"status invalide : {v!r}")
        return v

    @field_validator("owned")
    @classmethod
    def _check_owned(cls, v: int | None) -> int | None:
        if v is not None and v not in (0, 1):
            raise ValueError("owned doit valoir 0 ou 1")
        return v


class StatusUpdate(BaseModel):
    """POST /books/{id}/status — déplacement rapide entre statuts (§5).

    `finished_at` (ISO) n'a de sens que pour `read` : il crée une
    `read_entry` correspondante.
    """

    status: str
    finished_at: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in BOOK_STATUSES:
            raise ValueError(f"status invalide : {v!r}")
        return v


class BookOut(BaseModel):
    """Réponse `book` : modèle SQLModel + auteurs/tags/genres résolus + URLs locales.

    `cover_url`/`cover_thumb_url` sont construits depuis `cover_path`
    (chemin relatif au dossier `covers/`), servis par StaticFiles.
    """

    id: int
    title: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = None
    language: str | None = None
    description: str | None = None
    cover_path: str | None = None
    cover_source: str | None = None
    cover_url: str | None = None
    cover_thumb_url: str | None = None
    status: str
    owned: int
    rating: float | None = None
    current_page: int
    current_percent: float
    acquired_date: str | None = None
    openlibrary_work: str | None = None
    openlibrary_edition: str | None = None
    google_books_id: str | None = None
    koreader_md5: str | None = None
    notes: str | None = None
    created_at: str
    updated_at: str


class BookList(BaseModel):
    """Réponse de `GET /books` : items + métadonnées de pagination."""

    items: list[BookOut]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# TAXONOMIE — auteurs et labels (tags/genres)
# ---------------------------------------------------------------------------

class AuthorOut(BaseModel):
    id: int
    name: str
    openlibrary_key: str | None = None
    book_count: int = 0


class AuthorBooks(BaseModel):
    author: AuthorOut
    books: list[BookOut]


class LabelOut(BaseModel):
    id: int
    name: str
    kind: str  # genre | tag
    book_count: int = 0


class LabelList(BaseModel):
    items: list[LabelOut]
    total: int


# ---------------------------------------------------------------------------
# SESSIONS DE LECTURE
# ---------------------------------------------------------------------------

class ReadingSessionCreate(BaseModel):
    """Saisie manuelle d'une session (§5). `started_at` ISO (ou date seule).

    `pages_read` est dérivé (`end_page - start_page`) quand les deux pages
    sont fournies ; sinon il peut être saisi tel quel.
    """

    started_at: str
    ended_at: str | None = None
    duration_sec: int = Field(ge=0)
    start_page: int | None = Field(default=None, ge=0)
    end_page: int | None = Field(default=None, ge=0)
    pages_read: int | None = Field(default=None, ge=0)
    note: str | None = None


class ReadingSessionUpdate(BaseModel):
    """Mise à jour partielle d'une session."""

    started_at: str | None = None
    ended_at: str | None = None
    duration_sec: int | None = Field(default=None, ge=0)
    start_page: int | None = Field(default=None, ge=0)
    end_page: int | None = Field(default=None, ge=0)
    pages_read: int | None = Field(default=None, ge=0)
    note: str | None = None


class ReadingSessionOut(BaseModel):
    id: int
    book_id: int
    started_at: str
    ended_at: str | None = None
    duration_sec: int
    start_page: int | None = None
    end_page: int | None = None
    pages_read: int | None = None
    note: str | None = None
    source: str  # manual | timer | koreader
    koreader_hash: str | None = None  # idempotence imports KOReader (§4.2)
    created_at: str


class SessionList(BaseModel):
    items: list[ReadingSessionOut]
    total: int


# ---------------------------------------------------------------------------
# TIMER (session live)
# ---------------------------------------------------------------------------

class TimerStart(BaseModel):
    book_id: int


class TimerStop(BaseModel):
    book_id: int
    end_page: int = Field(ge=0)


# ---------------------------------------------------------------------------
# LECTURES (read_entry, relectures)
# ---------------------------------------------------------------------------

class ReadEntryCreate(BaseModel):
    started_at: str | None = None
    finished_at: str | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    review: str | None = None


class ReadEntryUpdate(BaseModel):
    started_at: str | None = None
    finished_at: str | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    review: str | None = None


class ReadEntryOut(BaseModel):
    id: int
    book_id: int
    started_at: str | None = None
    finished_at: str | None = None
    rating: float | None = None
    review: str | None = None
    created_at: str


class ReadEntryList(BaseModel):
    items: list[ReadEntryOut]
    total: int


# ---------------------------------------------------------------------------
# HIGHLIGHTS / CITATIONS
# ---------------------------------------------------------------------------

class HighlightCreate(BaseModel):
    """Création d'un highlight (§5) : `text` seul est obligatoire.

    `highlighted_at` (ISO) est la date du surlignage — distincte de
    `created_at`, qui est la date de saisie dans l'app. `location` et
    `source` ne sont pas exposés ici : `source` est forcé à `manual`
    (l'import KOReader écrira `koreader` en Phase 5), `location` est une
    donnée KOReader (xpointer/chapitre).
    """

    text: str = Field(min_length=1, max_length=20000)
    note: str | None = Field(default=None, max_length=5000)
    page: int | None = Field(default=None, ge=0)
    chapter: str | None = Field(default=None, max_length=500)
    color: str | None = Field(default=None, max_length=50)
    highlighted_at: str | None = None

    @field_validator("text")
    @classmethod
    def _check_text(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("le texte du highlight ne peut pas être vide")
        return v


class HighlightUpdate(BaseModel):
    """Mise à jour partielle d'un highlight."""

    text: str | None = Field(default=None, min_length=1, max_length=20000)
    note: str | None = Field(default=None, max_length=5000)
    page: int | None = Field(default=None, ge=0)
    chapter: str | None = Field(default=None, max_length=500)
    color: str | None = Field(default=None, max_length=50)
    highlighted_at: str | None = None

    @field_validator("text")
    @classmethod
    def _check_text(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("le texte du highlight ne peut pas être vide")
        return v


class HighlightOut(BaseModel):
    """Réponse `highlight`.

    `book_title` est résolu pour le flux global (`GET /highlights`) — le
    front doit savoir de quel livre vient une citation sans requête
    supplémentaire. Il est rempli aussi dans la liste par livre, où il est
    trivialement constant.
    """

    id: int
    book_id: int
    book_title: str | None = None
    text: str
    note: str | None = None
    page: int | None = None
    location: str | None = None
    chapter: str | None = None
    color: str | None = None
    source: str  # manual | koreader
    highlighted_at: str | None = None
    created_at: str


class HighlightList(BaseModel):
    items: list[HighlightOut]
    total: int


# ---------------------------------------------------------------------------
# KOREADER — import statistics.sqlite3 (§4, Phase 5)
# ---------------------------------------------------------------------------

class KoreaderSessionPreview(BaseModel):
    """Une session reconstruite (§4.2), telle qu'elle sera importée.

    `already_imported` : le `koreader_hash` existe déjà en base → l'import
    la sautera (idempotence).
    """

    koreader_hash: str
    started_at: str
    ended_at: str | None = None
    duration_sec: int
    start_page: int | None = None
    end_page: int | None = None
    pages_read: int | None = None
    already_imported: bool = False


class KoreaderCandidate(BaseModel):
    """Un livre de l'app suggéré comme rattachement probable (match flou
    titre+auteur, §4.3). La décision revient à l'utilisateur."""

    book_id: int
    title: str
    authors: list[str] = Field(default_factory=list)
    score: float  # 0..1 — similarité de titre (+ bonus auteur)


class KoreaderBookPreview(BaseModel):
    """Un livre détecté dans le fichier et son état de rattachement.

    `matched=True` : rattaché automatiquement via `koreader_md5` déjà
    persisté. Sinon `candidates` propose les livres de l'app les plus
    proches (titre+auteur) pour la confirmation manuelle.
    """

    koreader_book_id: int
    title: str
    authors: str
    md5: str | None = None
    total_sessions: int
    total_duration_sec: int
    matched: bool = False
    matched_book_id: int | None = None
    candidates: list[KoreaderCandidate] = Field(default_factory=list)


class KoreaderPreview(BaseModel):
    """Réponse de `POST /koreader/import` : le diff avant confirmation."""

    import_id: str  # sha256 du fichier ; requis par /import/confirm
    gap_sec: int
    books: list[KoreaderBookPreview]
    sessions: list[KoreaderSessionPreview]
    sessions_to_import: int
    sessions_skipped: int


class KoreaderMapping(BaseModel):
    """Rattachement choisi par l'utilisateur : livre KOReader → livre app."""

    koreader_book_id: int
    book_id: int


class KoreaderConfirmRequest(BaseModel):
    import_id: str
    mappings: list[KoreaderMapping] = Field(default_factory=list)


class KoreaderConfirmResult(BaseModel):
    """Résumé de `POST /koreader/import/confirm`."""

    import_id: str
    sessions_added: int
    sessions_skipped: int
    books_matched: int  # livres KOReader rattachés (md5 ou mapping)
    books_unmatched: int  # livres KOReader non rattachés (restent sans lien)


# ---------------------------------------------------------------------------
# STATS / DASHBOARD
# ---------------------------------------------------------------------------

class StatsOverview(BaseModel):
    """Totaux du dashboard (§5) : temps total, pages, streak, répartition."""

    total_books: int          # tous livres confondus
    books_owned: int          # owned = 1
    books_read: int           # status = read
    books_reading: int        # status = reading
    books_tbr: int            # status = tbr
    books_wishlist: int       # status = wishlist
    total_sessions: int
    total_duration_sec: int
    total_pages_read: int
    streak_days: int          # jours consécutifs avec ≥ 1 session
    avg_rating: float | None = None


class TimelinePoint(BaseModel):
    period: str  # "2026-08-14" (jour) | "2026-W33" (semaine) | "2026-08" (mois)
    duration_sec: int
    pages_read: int
    sessions: int


class StatsTimeline(BaseModel):
    points: list[TimelinePoint]


class BreakdownItem(BaseModel):
    label: str  # nom de genre / d'auteur
    duration_sec: int
    pages_read: int
    sessions: int


class StatsBreakdown(BaseModel):
    items: list[BreakdownItem]
