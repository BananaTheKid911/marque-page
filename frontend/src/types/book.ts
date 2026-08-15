/**
 * Types du frontend, dérivés du contrat d'API réel (backend/app/schemas.py,
 * §5 de SPEC.md). `Book` est la projection camelCase de `BookOut` produite
 * par le mapper de lib/api.ts — les champs exposés ici sont ceux que les
 * composants lisent réellement.
 *
 * Écarts assumés avec `BookOut` (choix front, documentés dans le mapper) :
 * - `authors` est un tableau de NOMS (`BookOut.authors: string[]`), plus de
 *   structure `{id, name}` — le détail id/via `GET /authors`.
 * - `labels` est éclaté en `tags`/`genres` (`BookOut` expose deux listes de
 *   noms, pas d'`id` par liaison).
 * - `owned`, `is_primary_reading` sont des booléens (`BookOut` : 0/1).
 * - `current_percent` devient `currentPercent` ; `price_paid` →
 *   `pricePaid` ; `tbr_rank` → `tbrRank` ; `cover_url` → `coverUrl`.
 * - `series_name`/`series_id`/`series_index` sont portés directement sur le
 *   livre (plus de table `Series` dédiée au rendu).
 */

/** `book.status` — SPEC.md §2 */
export type BookStatus =
  | "wishlist"
  | "tbr"
  | "reading"
  | "read"
  | "dnf"
  | "on_hold"

/** `label.kind` — SPEC.md §2 */
export type LabelKind = "genre" | "tag"

/** `GET /authors` — `AuthorOut` */
export interface Author {
  id: number
  name: string
  openlibraryKey?: string | null
  bookCount?: number
}

/** `GET /labels` — `LabelOut` */
export interface Label {
  id: number
  name: string
  kind: LabelKind
  bookCount?: number
}

/** `GET /series` — `SeriesOut` (le rang d'un tome vit sur le livre) */
export interface Series {
  id: number
  name: string
  bookCount?: number
}

/**
 * Format = physique / digital / audio, non exclusif : un livre peut cumuler
 * plusieurs formats. `owned` est porté PAR format, pas par livre.
 */
export type BookFormatType = "physique" | "digital" | "audio"

export interface BookFormat {
  type: BookFormatType
  owned: boolean
}

/** Projection camelCase de `BookOut` (backend/app/schemas.py). */
export interface Book {
  id: number
  title: string
  subtitle: string | null
  authors: string[]
  tags: string[]
  genres: string[]
  status: BookStatus
  /** chemin local servi par le backend, jamais un hotlink externe */
  coverUrl: string | null
  coverThumbUrl: string | null
  pageCount: number | null
  currentPage: number
  /** 0..1 */
  currentPercent: number
  rating: number | null
  publisher: string | null
  publishedDate: string | null
  language: string | null
  description: string | null
  /** `owned=1` (BookOut) — la Bibliothèque ne montre que les livres possédés */
  owned: boolean
  /**
   * Un seul livre `reading` à la fois porte `true` — exclusivité maintenue
   * côté backend (index partiel unique). Choix manuel exposé uniquement
   * depuis BookDetailPage (décision produit du 15/08/2026).
   */
  isPrimaryReading: boolean
  /** Série et numéro de tome, `null` si le livre n'appartient à aucune série. */
  seriesId: number | null
  seriesName: string | null
  seriesIndex: number | null
  /** Formats détenus/consultés — non exclusifs, `owned` varie par format. */
  formats: BookFormat[]
  /**
   * Prix payé et date d'achat, uniques par livre (pas par format). Jamais
   * renseignés pour `status === "wishlist"` (le backend refuse).
   */
  pricePaid: number | null
  purchasedAt: string | null
  /**
   * Pile à lire = liste curatée à la main, distincte du simple filtre
   * `status === "tbr"`. `tbrRank` porte l'ordre choisi (1 = prochain lu) ;
   * `tbrNote` est le motif optionnel affiché s'il existe.
   */
  tbrRank: number | null
  tbrNote: string | null
  createdAt: string
  updatedAt: string
}

/** `reading_session` — `ReadingSessionOut` (SPEC.md §5) */
export interface ReadingSession {
  id: number
  bookId: number
  startedAt: string
  endedAt: string | null
  durationSec: number
  startPage: number | null
  endPage: number | null
  pagesRead: number | null
  note: string | null
  source: "manual" | "timer" | "koreader"
}

/** `highlight` — `HighlightOut` (SPEC.md §5) */
export interface Highlight {
  id: number
  bookId: number
  bookTitle: string | null
  text: string
  note: string | null
  page: number | null
  chapter: string | null
  source: "manual" | "koreader"
  highlightedAt: string | null
  createdAt: string
}

/** Données affichées par le composant « Reprendre / En cours » */
export interface CurrentlyReading {
  book: Book
  /** durée de la session la plus récente, en secondes */
  lastSessionDurationSec: number
  /** nombre de sessions enregistrées sur ce livre */
  sessionCount: number
}

/** `GET /books` — `BookList` (page_size en snake_case, tel que servi) */
export interface BookList {
  items: Book[]
  total: number
  page: number
  page_size: number
}

export interface SessionList {
  items: ReadingSession[]
  total: number
}

export interface HighlightList {
  items: Highlight[]
  total: number
}

/** `GET /series/{id}/books` — `SeriesBooks` */
export interface SeriesBooks {
  series: Series
  books: Book[]
}

export interface NavItem {
  key: "library" | "tbr" | "add" | "stats" | "settings"
  label: string
  href: string
}
