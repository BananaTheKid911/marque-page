import { formatPercent } from "@/lib/format"
import type { Book } from "@/types/book"

interface BookProgressStatProps {
  book: Book
}

/**
 * Bloc de progression de la page Détail : le chiffre à 34px tabular-nums
 * (AGENTS.md « échelle typographique ») porte toute la hiérarchie, sans
 * couleur. N'apparaît que pour les statuts où une progression a un sens.
 */
export function BookProgressStat({ book }: BookProgressStatProps) {
  if (book.status === "wishlist") return null

  const percent = formatPercent(book.currentPercent)

  return (
    <section
      aria-label="Progression de lecture"
      className="rounded-[4px] bg-card p-5 shadow-card"
    >
      <div className="flex items-end justify-between">
        <span className="text-[34px] font-semibold leading-none tabular-nums text-ink">
          {percent}
        </span>
        <span className="text-[12.5px] tabular-nums text-ink-mute">
          p. {book.currentPage}
          {book.pageCount ? ` / ${book.pageCount}` : ""}
        </span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-line-2">
        <div className="h-full bg-ink" style={{ width: percent }} />
      </div>
    </section>
  )
}
