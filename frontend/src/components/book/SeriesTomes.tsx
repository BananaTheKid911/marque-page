import { Layers } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatTome } from "@/lib/format"
import { seriesForBook, seriesTomes } from "@/lib/mock-data"
import type { Book } from "@/types/book"

interface SeriesTomesProps {
  book: Book
}

/**
 * "Tome X de [Série]" + accès aux autres tomes de la bibliothèque (liens
 * simples vers /livres/:id, mock — pas de vraie navigation contextuelle).
 * Aucune couleur : le tome courant se distingue des autres par le contour
 * plein `--ink` + poids du texte, même levier que FormatBadges — pas un
 * "filet actif" de nav (ce n'est pas une nav), donc un contour plutôt
 * qu'un `border-bottom`.
 */
export function SeriesTomes({ book }: SeriesTomesProps) {
  const series = seriesForBook(book)
  if (!series || book.seriesIndex == null) return null

  const tomes = seriesTomes(book)

  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-center gap-1.5 text-[13.5px] text-ink-soft">
        <Layers className="h-3.5 w-3.5 shrink-0 text-ink-mute" strokeWidth={1.75} aria-hidden="true" />
        Tome <span className="tabular-nums">{formatTome(book.seriesIndex)}</span> de{" "}
        <span className="font-medium text-ink">{series.name}</span>
      </p>

      {tomes.length > 1 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={`Autres tomes de ${series.name}`}>
          {tomes.map((tome) => {
            const isCurrent = tome.id === book.id
            return (
              <li key={tome.id}>
                <a
                  href={`/livres/${tome.id}`}
                  aria-current={isCurrent ? "page" : undefined}
                  className={cn(
                    "inline-flex h-7 items-center rounded-[3px] border px-2 text-[12px] tabular-nums transition-colors",
                    isCurrent
                      ? "border-ink font-medium text-ink"
                      : "border-line text-ink-mute hover:border-ink hover:text-ink",
                  )}
                >
                  T. {formatTome(tome.seriesIndex ?? 0)}
                </a>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
