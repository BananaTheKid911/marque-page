/**
 * Types locaux à l'écran "Ajouter un livre" — pas encore de contrat d'API
 * réel côté backend pour la recherche (ISBN / titre-auteur). Forme
 * volontairement proche de ce que rendraient Open Library et Google Books
 * une fois normalisés côté backend, pour que frontend-dev n'ait qu'à
 * substituer la source des données, pas la forme consommée par l'UI.
 */

export type SearchSource = "openlibrary" | "google_books"

export const SOURCE_LABELS: Record<SearchSource, string> = {
  openlibrary: "Open Library",
  google_books: "Google Books",
}

/**
 * Une couverture candidate pour un résultat donné. `hasImage: false`
 * représente une entrée référencée mais sans scan disponible — un état
 * légitime (spec §4), pas une erreur : le livre reste sélectionnable sans
 * couverture, comme n'importe quel livre de la bibliothèque (BookCover
 * gère déjà `coverUrl: null`).
 */
export interface CoverCandidate {
  id: string
  source: SearchSource
  /** ex. "Édition La Volte, 2004" — sous-titre affiché sous la vignette */
  label: string
  hasImage: boolean
}

export interface SearchCandidate {
  id: string
  title: string
  subtitle?: string | null
  authors: string[]
  publisher?: string | null
  publishedDate?: string | null
  isbn?: string | null
  source: SearchSource
  covers: CoverCandidate[]
}
