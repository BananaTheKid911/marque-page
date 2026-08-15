export function formatPercent(ratio: number): string {
  return `${Math.round(ratio * 100)}%`
}

export function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.round((seconds % 3600) / 60)
  if (h > 0) return `${h} h ${m.toString().padStart(2, "0")}`
  return `${m} min`
}

export function formatAuthors(authors: { name: string }[]): string {
  return authors.map((a) => a.name).join(", ")
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
