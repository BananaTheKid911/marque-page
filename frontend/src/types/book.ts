/**
 * Types calqués sur le schéma SQLModel décrit dans SPEC.md §2 et l'API
 * §5, pour que frontend-dev n'ait qu'à brancher le client HTTP sans
 * retoucher la forme des données consommées par les composants visuels.
 *
 * Ce fichier n'est PAS le contrat d'API définitif — c'est une projection
 * côté front pensée pour l'affichage. Si le vrai payload diverge,
 * l'ajustement revient à frontend-dev / backend-dev.
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

export interface Author {
  id: number
  name: string
}

export interface Label {
  id: number
  name: string
  kind: LabelKind
}

/**
 * Série (inspirée de la table `book.series` de KOReader, SPEC.md §4.1) —
 * concept nouveau, absent du schéma actuel. `Book.seriesIndex` porte le
 * numéro de tome et autorise les décimales (1.5 pour un hors-série).
 */
export interface Series {
  id: number
  name: string
}

/**
 * Format = physique / digital / audio, non exclusif : un livre peut
 * cumuler plusieurs formats. `owned` est porté PAR format, pas par livre
 * — cas réel : édition papier achetée, version numérique seulement
 * empruntée/lue sans achat.
 */
export type BookFormatType = "physique" | "digital" | "audio"

export interface BookFormat {
  type: BookFormatType
  owned: boolean
}

export interface Book {
  id: number
  title: string
  subtitle?: string | null
  authors: Author[]
  labels: Label[]
  status: BookStatus
  /** chemin local servi par le backend, jamais un hotlink externe */
  coverUrl: string | null
  pageCount: number | null
  currentPage: number
  /** 0..1 */
  currentPercent: number
  rating: number | null
  /** métadonnées utilisées par la page Détail — absentes des mocks de grille */
  publisher?: string | null
  year?: number | null
  description?: string | null
  startedAt?: string | null
  finishedAt?: string | null
  /**
   * Un seul livre `reading` à la fois porte `true` — exclusivité maintenue
   * à la main dans les mocks (SQLModel/backend tranchera la contrainte
   * réelle). Choix manuel exposé uniquement depuis BookDetailPage, jamais
   * depuis la grille Bibliothèque (décision produit du 15/08/2026).
   */
  isPrimaryReading?: boolean
  /** Série et numéro de tome, `null`/absent si le livre n'appartient à aucune série. */
  seriesId?: number | null
  seriesIndex?: number | null
  /** Formats détenus/consultés — non exclusifs, `owned` varie par format. */
  formats?: BookFormat[]
  /**
   * Prix payé et date d'achat, uniques par livre (pas par format). Rempli
   * seulement au moment de l'achat réel : ne jamais afficher/remplir ces
   * deux champs pour `status === "wishlist"`.
   */
  pricePaid?: number | null
  purchasedAt?: string | null
  /**
   * Pile à lire = liste curatée à la main, distincte du simple filtre
   * `status === "tbr"` de la Bibliothèque. `tbrRank` porte l'ordre choisi
   * (1 = prochain lu) ; `tbrNote` est le motif optionnel affiché s'il existe.
   */
  tbrRank?: number | null
  tbrNote?: string | null
}

/** `reading_session` — SPEC.md §2 et §5 */
export interface ReadingSession {
  id: number
  bookId: number
  startedAt: string
  durationSec: number
  startPage: number | null
  endPage: number | null
  pagesRead: number | null
  source: "manual" | "timer" | "koreader"
}

/** `highlight` — SPEC.md §2 et §5 */
export interface Highlight {
  id: number
  bookId: number
  text: string
  note?: string | null
  page: number | null
  chapter?: string | null
  highlightedAt: string
  source: "manual" | "koreader"
}

/** Données affichées par le composant « Reprendre / En cours » */
export interface CurrentlyReading {
  book: Book
  /** durée de la session la plus récente, en secondes */
  lastSessionDurationSec: number
  /** nombre de sessions enregistrées sur ce livre */
  sessionCount: number
}

export interface NavItem {
  key: "library" | "tbr" | "add" | "stats" | "settings"
  label: string
  href: string
}
