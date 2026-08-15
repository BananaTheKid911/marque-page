export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  if (h > 0) return `${h} h ${m.toString().padStart(2, "0")}`
  return `${m} min`
}

/** "12:34" ou "1:02:03" — affichage du chrono de session en cours. */
export function formatClock(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  const mm = String(m).padStart(2, "0")
  const ss = String(s).padStart(2, "0")
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}

/** Noms d'auteurs tels que servis par BookOut (`authors: string[]`). */
export function formatAuthors(authors: string[]): string {
  return authors.join(", ")
}

/** Année isolée d'une `published_date` ("2026-08-10", "2026", "août 2026"). */
export function extractYear(publishedDate: string | null): number | null {
  if (!publishedDate) return null
  const match = /(19|20)\d{2}/.exec(publishedDate)
  return match ? Number(match[0]) : null
}

/** "2" ou "2.5" — jamais "2.0", pour les numéros de tome (décimales = hors-série). */
export function formatTome(index: number): string {
  return Number.isInteger(index) ? String(index) : index.toFixed(1)
}

const priceFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
})

/** "19,90 €" — prix payé, jamais affiché pour un livre `status === "wishlist"`. */
export function formatPrice(value: number): string {
  return priceFormatter.format(value)
}

const dayMonth = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long" })
const dayMonthYear = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "long",
  year: "numeric",
})

/** "12 août" — sans année, pour les listes récentes (sessions, imports). */
export function formatDate(iso: string): string {
  return dayMonth.format(new Date(iso))
}

/** "12 août 2026" — avec année, pour les dates isolées (ajout, fin de lecture). */
export function formatDateLong(iso: string): string {
  return dayMonthYear.format(new Date(iso))
}
