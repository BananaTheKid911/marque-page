/**
 * Types Stats — projection du contrat réel (backend/app/routers/stats.py).
 * Contrairement à `Book` (types/book.ts), ces formes ne sont PAS
 * renommées en camelCase : le backend les sert déjà en snake_case simple
 * et aucun mapper dédié n'existe encore côté `lib/api.ts` — StatsPage
 * consomme pour l'instant `lib/stats-mock.ts` (données représentatives,
 * pas de réseau réel). Câblage réel : TODO frontend-dev.
 */

export interface StatsOverview {
  total_books: number
  books_owned: number
  books_read: number
  books_reading: number
  books_tbr: number
  books_wishlist: number
  total_sessions: number
  total_duration_sec: number
  total_pages_read: number
  streak_days: number
  avg_rating: number | null
}

/** `GET /stats/timeline?range=` */
export type StatsRange = "day" | "week" | "month"

export interface TimelinePoint {
  /** "2026-08-14" (day), "2026-W33" (week), "2026-08" (month) */
  period: string
  duration_sec: number
  pages_read: number
  sessions: number
}

export interface StatsTimeline {
  points: TimelinePoint[]
}

export interface BreakdownItem {
  label: string
  duration_sec: number
  pages_read: number
  sessions: number
}

export interface StatsBreakdown {
  items: BreakdownItem[]
}
