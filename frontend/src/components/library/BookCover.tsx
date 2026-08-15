import { Link } from "react-router-dom"
import { formatAuthors, formatPercent } from "@/lib/format"
import { STATUS_LABELS } from "@/lib/constants"
import type { Book } from "@/types/book"

interface BookCoverProps {
  book: Book
  /**
   * Badge "T. X" sur le coin de la couverture — affiché uniquement quand
   * la grille est filtrée/triée par série (LibraryPage passe cette valeur
   * via BookGrid). Pas un attribut permanent de la couverture : hors
   * contexte série, la grille n'affiche jamais le numéro de tome.
   */
  tomeLabel?: string
}

/**
 * Les couvertures sont les héros (AGENTS.md) : ratio 2/3 strict, ombre
 * portée chaude, aucune bordure. Le statut "dnf" (abandonné) est un des
 * écrans candidats à une future couleur de signal — non tranchée, donc
 * traité ici en typographie pure (aucune couleur ajoutée).
 */
export function BookCover({ book, tomeLabel }: BookCoverProps) {
  const showProgress = book.status === "reading" && book.currentPercent > 0
  const showStatusCaption = book.status === "dnf" || book.status === "on_hold"

  return (
    <Link to={`/livres/${book.id}`} className="group block text-left">
      <div className="relative aspect-[2/3] overflow-hidden rounded-[2px] bg-line-2 shadow-cover transition-transform group-hover:-translate-y-0.5 group-focus-visible:-translate-y-0.5">
        {book.coverUrl && (
          <img
            src={book.coverUrl}
            alt=""
            className="h-full w-full object-cover"
            loading="lazy"
          />
        )}

        {tomeLabel && (
          <span className="absolute left-1.5 top-1.5 rounded-[2px] border border-line bg-card/90 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-[0.08em] tabular-nums text-ink-soft">
            {tomeLabel}
          </span>
        )}

        {showProgress && (
          <div className="absolute inset-x-0 bottom-0 h-[3px] bg-ink/15">
            <div
              className="h-full bg-ink"
              style={{ width: formatPercent(book.currentPercent) }}
            />
          </div>
        )}
      </div>

      <div className="mt-2">
        <h3 className="line-clamp-2 text-[14px] font-medium leading-snug text-ink">
          {book.title}
        </h3>
        <p className="mt-0.5 truncate text-[12.5px] text-ink-mute">
          {formatAuthors(book.authors)}
        </p>
        {showStatusCaption && (
          <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-ink-mute">
            {STATUS_LABELS[book.status]}
          </p>
        )}
      </div>
    </Link>
  )
}
