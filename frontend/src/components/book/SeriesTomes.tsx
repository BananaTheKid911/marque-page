import { Link } from "react-router-dom"
import { Layers } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatTome } from "@/lib/format"
import { listSeriesBooks } from "@/lib/api"
import { useAsyncData } from "@/lib/hooks"
import type { Book } from "@/types/book"

interface SeriesTomesProps {
  book: Book
}

/**
 * "Tome X de [Série]" + accès aux autres tomes de la bibliothèque (liens
 * vers /livres/:id). La série et l'index viennent de BookOut
 * (`series_name`/`series_index`) ; la liste des tomes est chargée depuis
 * GET /series/{id}/books, triée par numéro côté backend. Aucune couleur :
 * le tome courant se distingue par le contour plein `--ink` + poids du
 * texte.
 */
export function SeriesTomes({ book }: SeriesTomesProps) {
  const seriesId = book.seriesId
  const seriesIndex = book.seriesIndex

  // Hook inconditionnel : le garde est dans le fetcher (pas de série → null).
  const { data } = useAsyncData(
    () => (seriesId == null ? Promise.resolve(null) : listSeriesBooks(seriesId)),
    [seriesId],
  )

  if (!seriesId || !book.seriesName || seriesIndex == null) return null

  const tomes = data?.books ?? []

  return (
    <div className="flex flex-col gap-2">
      <p className="flex items-center gap-1.5 text-[13.5px] text-ink-soft">
        <Layers className="h-3.5 w-3.5 shrink-0 text-ink-mute" strokeWidth={1.75} aria-hidden="true" />
        Tome <span className="tabular-nums">{formatTome(seriesIndex)}</span> de{" "}
        <span className="font-medium text-ink">{book.seriesName}</span>
      </p>

      {tomes.length > 1 && (
        <ul className="flex flex-wrap gap-1.5" aria-label={`Autres tomes de ${book.seriesName}`}>
          {tomes.map((tome) => {
            const isCurrent = tome.id === book.id
            return (
              <li key={tome.id}>
                <Link
                  to={`/livres/${tome.id}`}
                  aria-current={isCurrent ? "page" : undefined}
                  className={cn(
                    "inline-flex h-7 items-center rounded-[3px] border px-2 text-[12px] tabular-nums transition-colors",
                    isCurrent
                      ? "border-ink font-medium text-ink"
                      : "border-line text-ink-mute hover:border-ink hover:text-ink",
                  )}
                >
                  T. {formatTome(tome.seriesIndex ?? 0)}
                </Link>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
