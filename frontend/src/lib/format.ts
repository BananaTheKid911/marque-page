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
