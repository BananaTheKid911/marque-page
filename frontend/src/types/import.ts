/**
 * Résultats d'opérations d'import (Book Track aujourd'hui, restauration de
 * backup éventuellement). Forme snake_case TEL QUE SERVIE par le backend
 * (backend/app/schemas.py `BooktrackImportResult`) — pas de projection
 * camelCase, contrairement à `types/book.ts` :
 *
 * - le résultat est éphémère : affiché une fois après l'import, jamais
 *   stocké ni manipulé par d'autres composants (alors que `Book` circule
 *   dans toute l'app et gagne à être camelCase) ;
 * - précédent identique dans le code : `types/stats.ts` définit ses formes
 *   "snake_case telles que servies" et `lib/api.ts` les retourne sans
 *   mapper ;
 * - `line_errors` est un tuple `[number, string]` — un mapper
 *   snake→camelCase n'aurait rien à renommer d'utile.
 *
 * En cas de divergence entre ce type et le payload réel, le signaler à
 * backend-dev plutôt que de contourner ici.
 */

/** `POST /import/booktrack` — `BooktrackImportResult` (§4.6 SPEC.md). */
export interface BooktrackImportResult {
  /**
   * lignes VALIDES lues dans le CSV (vérifié par exécution sur le MN56) :
   * les lignes en erreur ne sont PAS comptées ici, elles partent dans
   * `line_errors` (le backend fait `rows_parsed = len(parsed.rows)`).
   */
  rows_parsed: number
  /** livres insérés — sémantique ajout : un export rejoué ne recrée rien */
  books_created: number
  /** lignes déjà présentes (dédup par `booktrack_id`), ignorées */
  books_skipped: number
  /** [numéro de ligne, raison] — lignes non importables, sans bloquer le reste */
  line_errors: [number, string][]
  /** couvertures téléchargées en best-effort après le commit */
  covers_downloaded: number
  /** échecs de téléchargement d'image — n'affectent pas les données */
  covers_failed: number
}
