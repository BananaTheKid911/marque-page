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
