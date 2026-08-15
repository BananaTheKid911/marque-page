import { Play, Check, Bookmark, BookmarkCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { formatAuthors, formatDateLong, formatPrice } from "@/lib/format"
import { STATUS_LABELS } from "@/lib/mock-data"
import { SeriesTomes } from "./SeriesTomes"
import { FormatBadges } from "./FormatBadges"
import type { Book } from "@/types/book"

interface BookHeroProps {
  book: Book
}

/**
 * En-tête de la page Détail : couverture + identité + action primaire.
 * Empilé en mobile, deux colonnes à partir de 700px (mêmes seuils que le
 * reste du shell). Un seul bouton d'encre par écran (AGENTS.md) : c'est
 * celui-ci, "Démarrer une session" — le reste des actions est en outline,
 * y compris "Définir comme livre principal" qui n'est PAS un second point
 * de fixation malgré son état actif (contour + poids, jamais de remplissage).
 *
 * "Marquer comme en cours" / "Reprendre la lecture" (tbr / on_hold) est le
 * passage manuel explicite vers "reading" — troisième chemin décidé le
 * 15/08/2026, à côté des deux chemins automatiques côté backend (démarrer
 * une session, import KOReader). Reste en outline : ce n'est pas l'action
 * primaire de la ligne. Même icône Play que "Démarrer une session" (même
 * verbe visuel : lancer une lecture), mais en contour seulement — jamais
 * `fill-current` — pour rester subordonnée au Play plein du bouton d'encre.
 * Pas de bordure pointillée ici : dans FormatBadges.tsx, le pointillé porte
 * un sens déjà pris, "non possédé" sur l'axe format/possession — l'étendre
 * à "action pas encore engagée" écraserait cette convention plutôt que de
 * la réutiliser.
 */
export function BookHero({ book }: BookHeroProps) {
  const showCaption = book.status === "dnf" || book.status === "on_hold" || book.status === "wishlist"
  const canStartSession = book.status === "reading" || book.status === "tbr" || book.status === "on_hold"
  const hasPurchaseInfo =
    book.status !== "wishlist" && (book.pricePaid != null || book.purchasedAt != null)

  return (
    <div className="flex flex-col gap-6 @min-[700px]:flex-row">
      <div className="mx-auto w-40 shrink-0 @min-[700px]:mx-0 @min-[700px]:w-56">
        <div className="aspect-[2/3] overflow-hidden rounded-[2px] bg-line-2 shadow-cover">
          {book.coverUrl && (
            <img
              src={book.coverUrl}
              alt=""
              className="h-full w-full object-cover"
              loading="eager"
            />
          )}
        </div>
      </div>

      <div className="flex flex-1 flex-col gap-4">
        <div>
          {showCaption && (
            <p className="mb-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
              {STATUS_LABELS[book.status]}
            </p>
          )}
          <h1 className="text-balance text-[21px] font-semibold leading-snug text-ink">
            {book.title}
          </h1>
          {book.subtitle && (
            <p className="mt-0.5 text-[15px] italic text-ink-soft">{book.subtitle}</p>
          )}
          <p className="mt-1.5 text-[13.5px] text-ink-soft">{formatAuthors(book.authors)}</p>
        </div>

        <SeriesTomes book={book} />

        {book.labels.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {book.labels.map((label) => (
              <li key={`${label.kind}-${label.id}`}>
                <Badge variant="outline" className="text-[11px] font-normal text-ink-soft">
                  {label.name}
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <dl className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-ink-mute">
          {book.publisher && <div>{book.publisher}</div>}
          {book.year && <div className="tabular-nums">{book.year}</div>}
          {book.pageCount && <div className="tabular-nums">{book.pageCount} pages</div>}
          {book.rating && (
            <div className="tabular-nums">{book.rating.toFixed(1)} / 5</div>
          )}
        </dl>

        {book.formats && book.formats.length > 0 && <FormatBadges formats={book.formats} />}

        {hasPurchaseInfo && (
          <dl className="flex flex-wrap gap-x-6 gap-y-2">
            {book.pricePaid != null && (
              <div>
                <dt className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">
                  Prix payé
                </dt>
                <dd className="mt-0.5 text-[15px] tabular-nums text-ink">
                  {formatPrice(book.pricePaid)}
                </dd>
              </div>
            )}
            {book.purchasedAt && (
              <div>
                <dt className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">
                  Acheté le
                </dt>
                <dd className="mt-0.5 text-[13.5px] tabular-nums text-ink-soft">
                  {formatDateLong(book.purchasedAt)}
                </dd>
              </div>
            )}
          </dl>
        )}

        {book.description && (
          <p className="max-w-prose text-[15px] leading-relaxed text-ink-soft">
            {book.description}
          </p>
        )}

        <div className="mt-1 flex flex-wrap gap-2">
          {canStartSession && (
            <Button
              size="lg"
              className="h-11 rounded-[3px] px-5 text-[15px]"
            >
              <Play className="h-4 w-4 fill-current" aria-hidden="true" />
              Démarrer une session
            </Button>
          )}
          {(book.status === "tbr" || book.status === "on_hold") && (
            <Button
              variant="outline"
              size="lg"
              className="h-11 rounded-[3px] px-5 text-[15px]"
            >
              <Play className="h-4 w-4" aria-hidden="true" />
              {book.status === "on_hold" ? "Reprendre la lecture" : "Marquer comme en cours"}
            </Button>
          )}
          {book.status === "reading" && (
            <Button
              variant="outline"
              size="lg"
              aria-pressed={Boolean(book.isPrimaryReading)}
              className={cn(
                "h-11 rounded-[3px] px-5 text-[15px]",
                book.isPrimaryReading && "border-ink font-medium text-ink",
              )}
            >
              {book.isPrimaryReading ? (
                <BookmarkCheck className="h-4 w-4" aria-hidden="true" />
              ) : (
                <Bookmark className="h-4 w-4" aria-hidden="true" />
              )}
              {book.isPrimaryReading ? "Livre principal actuel" : "Définir comme livre principal"}
            </Button>
          )}
          {book.status !== "read" && (
            <Button
              variant="outline"
              size="lg"
              className="h-11 rounded-[3px] px-5 text-[15px]"
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Marquer comme lu
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
