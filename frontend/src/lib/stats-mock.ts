import type {
  BreakdownItem,
  StatsBreakdown,
  StatsOverview,
  StatsRange,
  StatsTimeline,
  TimelinePoint,
} from "@/types/stats"

/**
 * Données mock pour l'écran Statistiques — StatsPage.tsx n'appelle aucun
 * réseau réel. Les formes reproduisent exactement `backend/app/routers/
 * stats.py` (GET /stats/overview, /stats/timeline, /stats/by-genre,
 * /stats/by-author).
 *
 * TODO frontend-dev : remplacer ces quatre fonctions par de vrais appels
 * `lib/api.ts` (mêmes signatures, mêmes types de retour) quand le
 * câblage réseau de cet écran sera repris côté OpenCode.
 */

const MOCK_DELAY_MS = 260

function delayed<T>(value: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), MOCK_DELAY_MS))
}

const MOCK_OVERVIEW: StatsOverview = {
  total_books: 87,
  books_owned: 64,
  books_read: 41,
  books_reading: 2,
  books_tbr: 18,
  books_wishlist: 12,
  total_sessions: 236,
  total_duration_sec: 612_400,
  total_pages_read: 18_240,
  streak_days: 6,
  avg_rating: 4.2,
}

export function getStatsOverviewMock(): Promise<StatsOverview> {
  return delayed(MOCK_OVERVIEW)
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

function isoWeek(d: Date): string {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const dayNum = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  const week = Math.ceil(((date.getTime() - yearStart.getTime()) / 86_400_000 + 1) / 7)
  return `${date.getUTCFullYear()}-W${String(week).padStart(2, "0")}`
}

/** Répartition volontairement irrégulière (jours sans session inclus) — un
 * jeu de données parfaitement lisse cacherait les creux que l'écran doit
 * savoir représenter (barre à hauteur ~0, pas un point manquant). */
const DAY_PATTERN = [1200, 0, 2400, 1800, 0, 3600, 900, 2100, 0, 4200, 1500, 2700, 0, 3000]
const WEEK_PATTERN = [9800, 12400, 6200, 15600, 0, 11200, 14300, 8900]
const MONTH_PATTERN = [42_000, 51_000, 33_000, 0, 47_500, 60_200]

function buildTimeline(range: StatsRange): TimelinePoint[] {
  const today = new Date()
  const pattern = range === "day" ? DAY_PATTERN : range === "week" ? WEEK_PATTERN : MONTH_PATTERN
  const points: TimelinePoint[] = []

  pattern.forEach((duration_sec, indexFromOldest) => {
    const offset = pattern.length - 1 - indexFromOldest
    let period: string
    if (range === "day") {
      const d = new Date(today)
      d.setDate(d.getDate() - offset)
      period = d.toISOString().slice(0, 10)
    } else if (range === "week") {
      const d = new Date(today)
      d.setDate(d.getDate() - offset * 7)
      period = isoWeek(d)
    } else {
      const d = new Date(today.getFullYear(), today.getMonth() - offset, 1)
      period = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    }
    points.push({
      period,
      duration_sec,
      pages_read: Math.round(duration_sec / 90),
      sessions: duration_sec === 0 ? 0 : 1 + Math.round(duration_sec / 2000),
    })
  })

  return points
}

export function getStatsTimelineMock(range: StatsRange): Promise<StatsTimeline> {
  return delayed({ points: buildTimeline(range) })
}

// ---------------------------------------------------------------------------
// Répartition genre / auteur
// ---------------------------------------------------------------------------

function toBreakdown(rows: [string, number, number, number][]): StatsBreakdown {
  const items: BreakdownItem[] = rows
    .map(([label, duration_sec, pages_read, sessions]) => ({ label, duration_sec, pages_read, sessions }))
    .sort((a, b) => b.duration_sec - a.duration_sec)
  return { items }
}

const MOCK_BY_GENRE = toBreakdown([
  ["Science-fiction", 186_000, 5400, 62],
  ["Fantasy", 142_000, 4100, 48],
  ["Essai", 88_000, 2600, 31],
  ["Policier", 71_000, 2300, 25],
  ["Littérature blanche", 54_000, 1900, 19],
  ["Bande dessinée", 21_000, 900, 11],
])

const MOCK_BY_AUTHOR = toBreakdown([
  ["Becky Chambers", 64_000, 1800, 21],
  ["N.K. Jemisin", 52_000, 1500, 17],
  ["Sylvain Tesson", 41_000, 1200, 14],
  ["Ursula K. Le Guin", 38_000, 1100, 13],
  ["Pierre Lemaitre", 33_000, 1050, 12],
  ["Alain Damasio", 29_000, 900, 10],
  ["Naomi Novik", 24_000, 780, 9],
])

export function getStatsByGenreMock(): Promise<StatsBreakdown> {
  return delayed(MOCK_BY_GENRE)
}

export function getStatsByAuthorMock(): Promise<StatsBreakdown> {
  return delayed(MOCK_BY_AUTHOR)
}
