import { Link } from "react-router-dom"
import { ArrowRight, BookOpen, Play } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { formatAuthors, formatDuration, formatPercent } from "@/lib/format"
import type { CurrentlyReading } from "@/types/book"

interface CurrentlyReadingCardProps {
  /**
   * `null` quand aucun livre `reading` n'a été désigné manuellement comme
   * lecture principale (décision produit du 15/08/2026 : jamais de
   * fallback automatique — voir BookHero.tsx pour le geste "Définir comme
   * livre principal"). Les deux variantes dessinent alors un état vide
   * invitant à choisir dans la Pile à lire, plutôt que de se masquer ou
   * d'afficher un livre non choisi.
   */
  data: CurrentlyReading | null
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
  if (data === null) {
    return <EmptyCurrentlyReading variant={variant} className={className} />
  }

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
    <Link
      to={`/livres/${book.id}`}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-[3px] bg-ink text-paper transition-transform active:translate-y-px",
        variant === "banner"
          ? "h-11 min-w-11 px-4 text-[15px]"
          : "h-11 w-full text-[15px]",
      )}
    >
      <Play className="h-4 w-4 fill-current" aria-hidden="true" />
      Reprendre
    </Link>
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

/**
 * État vide des deux formes du composant — aucun livre `reading` désigné
 * comme lecture principale. Un des écrans "sans couverture" cités par
 * AGENTS.md : la place normalement occupée par la couverture devient un
 * cadre à trait fin (border-line-2, jamais de remplissage) plutôt que de
 * disparaître, pour que la carte garde la même silhouette dans les deux
 * états et ne "saute" pas visuellement une fois un livre choisi.
 *
 * Le bouton d'encre occupe exactement le rôle et l'emplacement de
 * "Reprendre" dans l'état rempli — ce n'est pas une deuxième masse noire
 * ajoutée à l'écran, c'est le même emplacement qui change de texte selon
 * l'état (AGENTS.md : un seul bouton d'encre par écran). La nav basse/du
 * haut a son propre bouton "Ajouter", indépendant de celui-ci.
 */
function EmptyCurrentlyReading({
  variant,
  className,
}: {
  variant: "banner" | "card"
  className?: string
}) {
  const placeholder = (
    <div
      className={cn(
        "flex aspect-[2/3] shrink-0 items-center justify-center rounded-[2px] border border-line-2",
        variant === "banner" ? "w-14" : "w-full max-w-[168px]",
      )}
    >
      <BookOpen
        className={variant === "banner" ? "h-4 w-4 text-ink-mute" : "h-7 w-7 text-ink-mute"}
        strokeWidth={1.5}
        aria-hidden="true"
      />
    </div>
  )

  if (variant === "banner") {
    return (
      <section
        aria-label="Aucun livre en cours"
        className={cn(
          "flex items-center gap-3 rounded-[4px] bg-card p-3 shadow-card",
          className,
        )}
      >
        {placeholder}
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-[13.5px] font-semibold text-ink">
            Aucun livre en cours
          </h2>
          <p className="truncate text-[12px] text-ink-soft">
            Choisis-en un dans ta pile à lire
          </p>
        </div>
        <Button
          asChild
          className="h-11 shrink-0 gap-1 rounded-[3px] px-3 text-[13px]"
        >
          <Link to="/pile-a-lire">
            Choisir
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </Button>
      </section>
    )
  }

  return (
    <section
      aria-label="Aucun livre en cours"
      className={cn(
        "flex flex-col items-center gap-4 rounded-[4px] bg-card p-5 py-10 text-center shadow-card",
        className,
      )}
    >
      {placeholder}
      <div>
        <h2 className="text-[17px] font-semibold text-ink">Aucun livre en cours</h2>
        <p className="mx-auto mt-1.5 max-w-[26ch] text-[13.5px] text-ink-mute">
          Choisis-en un dans ta pile à lire pour le retrouver ici.
        </p>
      </div>
      <Button asChild className="h-11 w-full rounded-[3px] text-[15px]">
        <Link to="/pile-a-lire">
          Aller à la pile à lire
          <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Link>
      </Button>
    </section>
  )
}
