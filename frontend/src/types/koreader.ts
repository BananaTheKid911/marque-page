/**
 * Types de l'écran d'import KOReader, dérivés du contrat réel
 * (backend/app/routers/koreader.py + backend/app/schemas.py, §4/§5 de
 * SPEC.md). Projection camelCase, même convention que `types/book.ts` —
 * le mapper snake_case → camelCase sera écrit par frontend-dev dans
 * `lib/api.ts` au moment du branchement réseau. Ici : formes exactes,
 * pas d'appel réseau.
 *
 * Écarts avec les schémas Pydantic (mêmes noms de champs, casse near :
 * `import_id` → `importId`, `koreader_book_id` → `koreaderBookId`,
 * `matched_book_id` → `matchedBookId`, `total_sessions` →
 * `totalSessions`, `total_duration_sec` → `totalDurationSec`,
 * `sessions_to_import` → `sessionsToImport`, `sessions_skipped` →
 * `sessionsSkipped`, `already_imported` → `alreadyImported`,
 * `sessions_added` → `sessionsAdded`, `books_matched` → `booksMatched`,
 * `books_unmatched` → `booksUnmatched`).
 */

/** `KoreaderCandidate` — suggestion de rattachement flou, score 0..1. */
export interface KoreaderCandidate {
  bookId: number
  title: string
  authors: string[]
  score: number
}

/** `KoreaderBookPreview` — un livre du fichier statistics.sqlite3. */
export interface KoreaderBookPreview {
  koreaderBookId: number
  title: string
  authors: string[]
  md5: string
  totalSessions: number
  totalDurationSec: number
  /** `true` = rattaché automatiquement par MD5 exact, jamais par le flou seul. */
  matched: boolean
  matchedBookId: number | null
  /** Jusqu'à 3, uniquement présent si `matched === false`. */
  candidates: KoreaderCandidate[]
}

/** `KoreaderSessionPreview` — une session reconstruite (comptage uniquement ici). */
export interface KoreaderSessionPreview {
  koreaderHash: string
  startedAt: string
  endedAt: string | null
  durationSec: number
  startPage: number | null
  endPage: number | null
  pagesRead: number | null
  alreadyImported: boolean
}

/** `KoreaderPreview` — réponse de `POST /koreader/import`. */
export interface KoreaderPreview {
  importId: string
  /** Seuil d'inactivité (secondes) utilisé pour reconstruire les sessions. */
  gapSec: number
  books: KoreaderBookPreview[]
  sessions: KoreaderSessionPreview[]
  sessionsToImport: number
  sessionsSkipped: number
}

/** Un rattachement choisi sur l'écran de matching manuel. */
export interface KoreaderMapping {
  koreaderBookId: number
  bookId: number
}

/** `KoreaderConfirmRequest` — corps de `POST /koreader/import/confirm`. */
export interface KoreaderConfirmRequest {
  importId: string
  mappings: KoreaderMapping[]
}

/** `KoreaderConfirmResult` — réponse finale de la confirmation. */
export interface KoreaderConfirmResult {
  importId: string
  sessionsAdded: number
  sessionsSkipped: number
  booksMatched: number
  booksUnmatched: number
}
