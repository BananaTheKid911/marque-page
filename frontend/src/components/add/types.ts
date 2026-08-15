/**
 * Types locaux à l'écran "Ajouter un livre" — projection du contrat réel
 * (backend/app/routers/lookup.py + schemas.py, §3/§5). Le mapper
 * snake_case → ces formes vit dans lib/api.ts / AddBookPage.tsx.
 *
 * Écarts documentés avec le backend (normalisés au branchement) :
 * - `source` : le backend sert "google", l'UI attend "google_books".
 * - `CoverCandidate` : le backend sert `{url, width, height, source}` ;
 *   `label` est construit côté front depuis la résolution, `hasImage` vaut
 *   toujours `true` (le backend ne renvoie que des variantes réelles).
 * - `SearchCandidate.work` (clé Open Library) est nécessaire pour
 *   `GET /lookup/covers?work=` au moment de la sélection.
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
  /** Clé de sélection (CoverPicker) — l'URL de la variante, unique. */
  id: string
  /** URL de la variante (externe) — c'est elle qui part dans POST /books
   * (le backend la télécharge localement, jamais de hotlink). */
  url: string
  source: SearchSource
  /** ex. "600×900 — grande résolution" — construit depuis le contrat réel */
  label: string
  hasImage: boolean
}

export interface SearchCandidate {
  /** clé stable : openlibrary_work / edition / google_books_id / isbn */
  id: string
  title: string
  subtitle?: string | null
  authors: string[]
  publisher?: string | null
  publishedDate?: string | null
  /** ISBN préféré (13 si connu, sinon 10) — pour la création et les variantes */
  isbn?: string | null
  /** clé Open Library du work — nécessaire pour GET /lookup/covers */
  work: string | null
  pageCount?: number | null
  language?: string | null
  description?: string | null
  source: SearchSource
  covers: CoverCandidate[]
}
