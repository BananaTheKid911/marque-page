/**
 * Types Stats — projection du contrat réel (backend/app/routers/stats.py).
 * Formes non renommées en camelCase : le backend les sert déjà en
 * snake_case simple et lib/api.ts les passe telles quelles (StatsPage).
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
