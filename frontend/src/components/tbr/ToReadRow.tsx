import type { HTMLAttributes } from "react"
import { Link } from "react-router-dom"
import { GripVertical } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatAuthors } from "@/lib/format"
import type { Book } from "@/types/book"

interface ToReadRowProps {
  book: Book
  position: number
  /**
   * Handlers dnd-kit (useSortable) à poser sur la poignée : seul le grip
   * déclenche le drag, le reste de la ligne reste une navigation vers le
   * Détail. `touch-none` sur la poignée pour que le drag tactile fonctionne.
   */
  dragHandleProps?: HTMLAttributes<HTMLSpanElement>
  isDragging?: boolean
}

/**
 * Ligne de la pile à lire — "la sélection", une liste curatée à la main
 * (`tbrRank`, ordre POSTé via /books/tbr/reorder), pas le simple filtre
 * `status === "tbr"` de la Bibliothèque. Volontairement une liste, pas une
 * grille : la Bibliothèque montre un catalogue, la PAL montre une file
 * d'intention. Le levier de hiérarchie est l'ordinal (poids/taille), pas
 * une couleur — aucun bouton rempli ici : la masse noire de l'écran est
 * ailleurs (AGENTS.md, un seul bouton d'encre par écran). Le rang réutilise
 * le palier "titre de section" (19–22px, AGENTS.md).
 */
export function ToReadRow({ book, position, dragHandleProps, isDragging }: ToReadRowProps) {
  return (
    <div
      className={cn(
        "flex min-h-[44px] items-center gap-3 rounded-[4px] transition-colors hover:bg-card focus-within:bg-card @min-[700px]:gap-4",
        isDragging && "bg-card",
      )}
    >
      <span
        {...dragHandleProps}
        aria-label={`Réordonner ${book.title}`}
        className="ml-1 flex shrink-0 cursor-grab touch-none items-center rounded-[3px] p-1 text-ink-mute/50 transition-colors hover:text-ink active:cursor-grabbing @min-[700px]:ml-2"
      >
        <GripVertical className="h-4 w-4" aria-hidden="true" />
      </span>

      <Link
        to={`/livres/${book.id}`}
        className="flex min-h-[44px] flex-1 items-center gap-3 py-2.5 pr-2 @min-[700px]:gap-4 @min-[700px]:pr-3"
      >
        <span className="w-7 shrink-0 text-right text-[19px] font-semibold leading-none tabular-nums text-ink @min-[1200px]:w-8 @min-[1200px]:text-[22px]">
          {position}
        </span>

        <div className="aspect-[2/3] w-11 shrink-0 overflow-hidden rounded-[2px] bg-line-2 shadow-cover @min-[700px]:w-14">
          {book.coverUrl && (
            <img
              src={book.coverUrl}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          )}
        </div>

        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[14px] font-medium text-ink @min-[700px]:text-[15px]">
            {book.title}
          </h3>
          <p className="truncate text-[12.5px] text-ink-mute">{formatAuthors(book.authors)}</p>
          {[...book.genres, ...book.tags].length > 0 && (
            <p className="mt-0.5 truncate text-[11px] uppercase tracking-[0.1em] text-ink-mute">
              {[...book.genres, ...book.tags].join(" · ")}
            </p>
          )}
          {book.tbrNote && (
            <p className="mt-1 line-clamp-2 text-[12.5px] italic leading-snug text-ink-soft">
              « {book.tbrNote} »
            </p>
          )}
        </div>

        {book.pageCount && (
          <span className="shrink-0 self-start text-[12.5px] tabular-nums text-ink-mute">
            {book.pageCount} p.
          </span>
        )}
      </Link>
    </div>
  )
}
