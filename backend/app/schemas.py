"""Schémas Pydantic de l'API Marque-page (préfixe /api/v1).

Ce fichier porte exclusivement les modèles de **requête/réponse HTTP** :
lookup (§3), couvertures, CRUD book (§5). Les modèles de persistance
vivent dans app.models (SQLModel, miroir du DDL §2).

Conventions :
- `Lookup*` = données externes agrégées (Open Library + Google Books).
- `Book*` = données de la base (le `Book` SQLModel n'est jamais exposé brut).
- Les URLs de couverture servies sont toujours locales (`/covers/...`).
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# LOOKUP — données agrégées depuis Open Library / Google Books
# ---------------------------------------------------------------------------

#: Statuts de livre valides (SPEC.md §2). `wishlist` n'est plus un statut
#: depuis le 16/08/2026 : un livre souhaité porte `is_wishlist=1` (flag
#: indépendant), et la seule sortie de wishlist est `POST /books/{id}/acquire`.
BOOK_STATUSES = {"tbr", "reading", "read", "dnf", "on_hold"}

#: Types de livre (décision 16/08/2026) — CHECK `ck_book_type` en base.
BOOK_TYPES = ("livre", "manga", "comics", "manhwa")

#: Formats non exclusifs d'un livre (décision produit 15/08), en accord avec
#: la CHECK constraint `ck_book_format_type` de la table `book_format`.
BOOK_FORMAT_TYPES = ("physique", "digital", "audio")


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

class BookFormatOut(BaseModel):
    """Un format de livre tel que renvoyé par l'API.

    `type` et `owned` sont portés PAR format (décision produit 15/08) : un
    livre peut avoir le papier acheté (`owned=true`) et le digital emprunté
    (`owned=false`) — deux lignes distinctes de `book_format`.
    """

    type: Literal["physique", "digital", "audio"]
    owned: bool


class BookFormatIn(BaseModel):
    """Entrée d'un format sur create/patch. `owned` est explicite (le front
    décide du défaut visuel) ; les doublons de `type` sont rejetés par le
    validator du payload parent."""

    type: Literal["physique", "digital", "audio"]
    owned: bool


class BookCreate(BaseModel):
    """Création d'un livre (depuis lookup ou manuel). Tous les champs sont
    optionnels sauf `title`. `cover_url` déclenche le téléchargement local.
    `tags` et `genres` sont des listes de noms, upsertées dans `label`.
    `series` est un NOM de série, upserté par nom unique (table `series`) ;
    `formats` remplace la liste complète des formats du livre."""

    title: str = Field(min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    series: str | None = Field(default=None, max_length=300)  # nom, upserté
    series_index: float | None = Field(default=None, ge=0)  # décimales : 1.5 hors-série
    formats: list[BookFormatIn] | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    language: str | None = None
    description: str | None = None
    status: str = "tbr"
    is_wishlist: int = 0  # 1 = ajout direct à la wishlist ; `status` sans objet
    type: str = "livre"  # livre | manga | comics | manhwa
    owned: int = 1
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    current_page: int = Field(default=0, ge=0)
    acquired_date: str | None = None
    price_paid: float | None = Field(default=None, ge=0)  # jamais en wishlist
    purchased_at: str | None = None  # jamais en wishlist
    is_primary_reading: bool = False  # exclusif parmi les reading
    tbr_rank: int | None = Field(default=None, ge=1)  # sélection PAL, hors statut
    tbr_note: str | None = Field(default=None, max_length=2000)
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

    @field_validator("is_wishlist")
    @classmethod
    def _check_is_wishlist(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("is_wishlist doit valoir 0 ou 1")
        return v

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in BOOK_TYPES:
            raise ValueError(f"type invalide : {v!r}")
        return v

    @field_validator("owned")
    @classmethod
    def _check_owned(cls, v: int) -> int:
        if v not in (0, 1):
            raise ValueError("owned doit valoir 0 ou 1")
        return v

    @field_validator("formats")
    @classmethod
    def _check_formats(cls, v: list[BookFormatIn] | None) -> list[BookFormatIn] | None:
        if v is None:
            return v
        seen: set[str] = set()
        for fmt in v:
            if fmt.type in seen:
                raise ValueError(f"format dupliqué : {fmt.type!r}")
            seen.add(fmt.type)
        return v


class BookUpdate(BaseModel):
    """Mise à jour partielle d'un livre. `authors`, `tags`, `genres` et
    `formats` remplaçant la liste complète quand fournis (une liste vide les
    vide). `cover_url` déclenche un nouveau téléchargement local.
    `series` : nom upserté ; une chaîne vide retire la série (`None` = ne
    pas toucher). `is_primary_reading=true` désigne le livre principal et
    déset les autres (`false` le déset)."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    subtitle: str | None = Field(default=None, max_length=500)
    authors: list[str] | None = None
    tags: list[str] | None = None
    genres: list[str] | None = None
    series: str | None = Field(default=None, max_length=300)  # "" = retirer
    series_index: float | None = Field(default=None, ge=0)
    formats: list[BookFormatIn] | None = None
    isbn10: str | None = None
    isbn13: str | None = None
    publisher: str | None = None
    published_date: str | None = None
    page_count: int | None = Field(default=None, ge=0)
    language: str | None = None
    description: str | None = None
    status: str | None = None
    type: str | None = None  # livre | manga | comics | manhwa
    owned: int | None = None
    rating: float | None = Field(default=None, ge=0.5, le=5.0)
    current_page: int | None = Field(default=None, ge=0)
    acquired_date: str | None = None
    price_paid: float | None = Field(default=None, ge=0)
    purchased_at: str | None = None
    is_primary_reading: bool | None = None
    tbr_rank: int | None = Field(default=None, ge=1)
    tbr_note: str | None = Field(default=None, max_length=2000)
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

    @field_validator("type")
    @classmethod
    def _check_type(cls, v: str | None) -> str | None:
        if v is not None and v not in BOOK_TYPES:
            raise ValueError(f"type invalide : {v!r}")
        return v

    @field_validator("owned")
    @classmethod
    def _check_owned(cls, v: int | None) -> int | None:
        if v is not None and v not in (0, 1):
            raise ValueError("owned doit valoir 0 ou 1")
        return v

    @field_validator("formats")
    @classmethod
    def _check_formats(cls, v: list[BookFormatIn] | None) -> list[BookFormatIn] | None:
        if v is None:
            return v
        seen: set[str] = set()
        for fmt in v:
            if fmt.type in seen:
                raise ValueError(f"format dupliqué : {fmt.type!r}")
            seen.add(fmt.type)
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


class TbrReorder(BaseModel):
    """POST /books/tbr/reorder — nouvel ordre de la Pile à lire (15/08).

    `book_ids` porte l'ordre COMPLET voulu (1 = prochain lu) : la liste
    fournie est la sélection, les livres encore `tbr` non listés perdent
    leur rang (fin de liste). Chaque id doit référencer un livre `tbr`
    existant, sans doublon — toute entrée invalide est rejetée (422) avant
    toute modification (atomicité).
    """

    book_ids: list[int] = Field(min_length=1, max_length=500)

    @field_validator("book_ids")
    @classmethod
    def _check_unique(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("book_ids ne doit pas contenir de doublon")
        return v


class BookOut(BaseModel):
    """Réponse `book` : modèle SQLModel + auteurs/tags/genres/formats/série
    résolus + URLs locales.

    `cover_url`/`cover_thumb_url` sont construits depuis `cover_path`
    (chemin relatif au dossier `covers/`), servis par StaticFiles.
    `is_primary_reading` et `is_wishlist` sont des booléens (colonnes 0/1) ;
    `formats` liste les formats avec leur possession par format.
    """

    id: int
    title: str
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    series_id: int | None = None
    series_name: str | None = None
    series_index: float | None = None
    formats: list[BookFormatOut] = Field(default_factory=list)

    @field_validator("series_index", mode="before")
    @classmethod
    def _series_index_to_float(cls, v):
        """La colonne NUMERIC de SQLite est relue en Decimal : le normaliser
        en float à la validation, sinon la sérialisation émet un warning
        Pydantic (type attendu `float`)."""
        if isinstance(v, Decimal):
            return float(v)
        return v
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
    is_wishlist: bool = False  # la colonne est un 0/1
    type: str = "livre"  # livre | manga | comics | manhwa
    owned: int
    rating: float | None = None
    current_page: int
    current_percent: float
    acquired_date: str | None = None
    price_paid: float | None = None
    purchased_at: str | None = None
    is_primary_reading: bool = False
    tbr_rank: int | None = None
    tbr_note: str | None = None
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
# SAUVEGARDE — export / restauration
# ---------------------------------------------------------------------------

class RestoreResult(BaseModel):
    """Résumé de `POST /import` — restauration d'un backup `GET /export`.

    `exported_at` provient du JSON restauré (pour l'affichage « restauré
    depuis le backup du … ») ; les compteurs portent ce qui a été réinséré.
    """

    exported_at: str | None = None
    books: int = 0
    sessions: int = 0
    highlights: int = 0
    reads: int = 0
    series: int = 0
    covers_written: int = 0


class BooktrackImportResult(BaseModel):
    """Résumé de `POST /import/booktrack` — import CSV Book Track (§4.6).

    Sémantique AJOUT : `books_created` = livres insérés, `books_skipped` =
    lignes déjà présentes (dédup par `booktrack_id`, re-jeu du fichier
    sans doublon). `line_errors` porte les lignes non importables (id ou
    titre manquant) sans bloquer le reste. Les couvertures sont téléchargées
    en best-effort après le commit : un échec d'image ne fait pas échouer
    l'import des données.
    """

    rows_parsed: int = 0
    books_created: int = 0
    books_skipped: int = 0
    line_errors: list[tuple[int, str]] = []
    covers_downloaded: int = 0
    covers_failed: int = 0


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


class SeriesOut(BaseModel):
    """Une série (décision produit 15/08) : nom unique + nombre de livres
    liés. Le rang d'un tome vit sur le livre (`series_index`), pas ici."""

    id: int
    name: str
    book_count: int = 0


class SeriesBooks(BaseModel):
    series: SeriesOut
    books: list[BookOut]


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
    books_wishlist: int       # is_wishlist = 1
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
