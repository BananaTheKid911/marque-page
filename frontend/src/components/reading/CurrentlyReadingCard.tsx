import { Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatAuthors, formatDuration, formatPercent } from "@/lib/format"
import type { CurrentlyReading } from "@/types/book"

interface CurrentlyReadingCardProps {
  data: CurrentlyReading
  /**
   * "banner" : bandeau en tête de bibliothèque, mobile (< 700px).
   * "card"   : carte latérale fixe, >= 700px (280px) et >= 1200px
   *            tactile (300px).
   *
   * Un seul composant, deux formes (AGENTS.md) : mêmes données, mêmes
   * sous-éléments (couverture, progression, bouton Reprendre), disposés
   * différemment. La forme est choisie par le shell — qui la décide lui
   * -même via @container — pas par ce composant : sa propre boîte n'a
   * pas de largeur stable qui permettrait de le déduire seul (une carte
   * de 280px et un bandeau plein-largeur mobile peuvent se chevaucher en
   * pixels).
   */
  variant: "banner" | "card"
  className?: string
}

export function CurrentlyReadingCard({
  data,
  variant,
  className,
}: CurrentlyReadingCardProps) {
  const { book, lastSessionDurationSec, sessionCount } = data
  const percent = formatPercent(book.currentPercent)

  const cover = (
    <div
      className={cn(
        "aspect-[2/3] shrink-0 overflow-hidden rounded-[2px] bg-line-2 shadow-cover",
        variant === "banner" ? "w-14" : "w-full max-w-[168px]",
      )}
    >
      {book.coverUrl && (
        <img
          src={book.coverUrl}
          alt=""
          className="h-full w-full object-cover"
          loading="eager"
        />
      )}
    </div>
  )

  const resumeButton = (
    <a
      href={`/livres/${book.id}`}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[3px] bg-ink text-paper transition-transform active:translate-y-px",
        variant === "banner"
          ? "h-11 min-w-11 px-4 text-[15px]"
          : "h-11 w-full text-[15px]",
      )}
    >
      <Play className="h-4 w-4 fill-current" aria-hidden="true" />
      Reprendre
    </a>
  )

  if (variant === "banner") {
    return (
      <section
        aria-label="Livre en cours"
        className={cn(
          "flex items-center gap-3 rounded-[4px] bg-card p-3 shadow-card",
          className,
        )}
      >
        {cover}
        <div className="min-w-0 flex-1">
          <p className="mb-0.5 text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">
            En cours
          </p>
          <h2 className="truncate text-[15px] font-semibold text-ink">
            {book.title}
          </h2>
          <p className="truncate text-[13px] text-ink-soft">
            {formatAuthors(book.authors)}
          </p>
          <div className="mt-1.5 flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-line-2">
              <div
                className="h-full bg-ink"
                style={{ width: percent }}
              />
            </div>
            <span className="shrink-0 text-[12px] tabular-nums text-ink-mute">
              {percent}
            </span>
          </div>
        </div>
        {resumeButton}
      </section>
    )
  }

  return (
    <section
      aria-label="Livre en cours"
      className={cn(
        "flex flex-col gap-4 rounded-[4px] bg-card p-5 shadow-card",
        className,
      )}
    >
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">
        En cours
      </p>

      {cover}

      <div>
        <h2 className="text-balance text-[21px] font-semibold leading-snug text-ink">
          {book.title}
        </h2>
        <p className="mt-1 text-[13.5px] text-ink-soft">
          {formatAuthors(book.authors)}
        </p>
      </div>

      <div className="flex items-end justify-between">
        <span className="text-[34px] font-semibold leading-none tabular-nums text-ink">
          {percent}
        </span>
        <span className="text-[12px] tabular-nums text-ink-mute">
          p. {book.currentPage}
          {book.pageCount ? ` / ${book.pageCount}` : ""}
        </span>
      </div>

      <div className="h-1.5 overflow-hidden rounded-full bg-line-2">
        <div className="h-full bg-ink" style={{ width: percent }} />
      </div>

      <dl className="flex items-center justify-between text-[12px] text-ink-mute">
        <div>
          <dt className="inline">Dernière session </dt>
          <dd className="inline tabular-nums text-ink-soft">
            {formatDuration(lastSessionDurationSec)}
          </dd>
        </div>
        <div>
          <dt className="inline">Sessions </dt>
          <dd className="inline tabular-nums text-ink-soft">{sessionCount}</dd>
        </div>
      </dl>

      {resumeButton}
    </section>
  )
}
