import { Play, Check, Bookmark, BookmarkCheck } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { extractYear, formatAuthors, formatClock, formatDateLong, formatPrice } from "@/lib/format"
import { STATUS_LABELS } from "@/lib/constants"
import { SeriesTomes } from "./SeriesTomes"
import { FormatBadges } from "./FormatBadges"
import { SessionEndControl } from "./SessionEndControl"
import type { Book } from "@/types/book"

/** État du chrono de session, tel que consommé par le bouton primaire. */
export interface BookHeroTimerState {
  running: boolean
  /** secondes écoulées depuis le début, rafraîchies chaque seconde */
  elapsedSec: number
}

interface BookHeroProps {
  book: Book
  /** `null` = aucun chrono ouvert pour ce livre */
  timer?: BookHeroTimerState | null
  /** pendant une mutation : désactive les boutons pour éviter les doubles POST */
  busy?: boolean
  /** message d'erreur de la dernière mutation, affiché près des actions */
  error?: string | null
  onStartSession?: () => void
  onMarkReading?: () => void
  onTogglePrimary?: () => void
  onMarkRead?: () => void
  /**
   * Le clic sur "Arrêter le chrono" ouvre `SessionEndControl` à la place du
   * bouton (AGENTS.md : masse noire unique, elle se déplace du déclencheur
   * au bouton de confirmation) plutôt que d'appeler `onStopSession`
   * directement. `endSessionOpen` est piloté par le parent pour survivre
   * à un re-render sans état local dupliqué.
   */
  endSessionOpen?: boolean
  onRequestEndSession?: () => void
  onConfirmEndSession?: (endPage: number) => void
  onCancelEndSession?: () => void
}

/**
 * En-tête de la page Détail : couverture + identité + action primaire.
 * Empilé en mobile, deux colonnes à partir de 700px (mêmes seuils que le
 * reste du shell). Un seul bouton d'encre par écran (AGENTS.md) : c'est
 * celui-ci — quand un chrono est ouvert, il devient "Arrêter le chrono"
 * avec la durée écoulée (même emplacement, même masse noire).
 *
 * "Marquer comme en cours" / "Reprendre la lecture" (tbr / on_hold) est le
 * passage manuel explicite vers "reading" — troisième chemin décidé le
 * 15/08/2026, à côté des deux chemins automatiques côté backend (démarrer
 * une session, import KOReader). Reste en outline : ce n'est pas l'action
 * primaire de la ligne.
 */
export function BookHero({
  book,
  timer = null,
  busy = false,
  error = null,
  onStartSession,
  onMarkReading,
  onTogglePrimary,
  onMarkRead,
  endSessionOpen = false,
  onRequestEndSession,
  onConfirmEndSession,
  onCancelEndSession,
}: BookHeroProps) {
  const showCaption = book.status === "dnf" || book.status === "on_hold" || book.status === "wishlist"
  const canStartSession = book.status === "reading" || book.status === "tbr" || book.status === "on_hold"
  const hasPurchaseInfo =
    book.status !== "wishlist" && (book.pricePaid != null || book.purchasedAt != null)
  const year = extractYear(book.publishedDate)
  const allLabels = [...book.genres, ...book.tags]

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

        {allLabels.length > 0 && (
          <ul className="flex flex-wrap gap-1.5">
            {allLabels.map((label) => (
              <li key={label}>
                <Badge variant="outline" className="text-[11px] font-normal text-ink-soft">
                  {label}
                </Badge>
              </li>
            ))}
          </ul>
        )}

        <dl className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12.5px] text-ink-mute">
          {book.publisher && <div>{book.publisher}</div>}
          {year && <div className="tabular-nums">{year}</div>}
          {book.pageCount && <div className="tabular-nums">{book.pageCount} pages</div>}
          {book.rating && (
            <div className="tabular-nums">{book.rating.toFixed(1)} / 5</div>
          )}
        </dl>

        {book.formats.length > 0 && <FormatBadges formats={book.formats} />}

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
          {timer?.running && endSessionOpen ? (
            <SessionEndControl
              currentPage={book.currentPage}
              totalPages={book.pageCount}
              busy={busy}
              onConfirm={(endPage) => onConfirmEndSession?.(endPage)}
              onCancel={() => onCancelEndSession?.()}
            />
          ) : timer?.running ? (
            <Button
              size="lg"
              className="h-11 rounded-[3px] px-5 text-[15px]"
              onClick={onRequestEndSession}
              disabled={busy}
            >
              <Play className="h-4 w-4 fill-current" aria-hidden="true" />
              Arrêter le chrono {formatClock(timer.elapsedSec)}
            </Button>
          ) : (
            canStartSession && (
              <Button size="lg" className="h-11 rounded-[3px] px-5 text-[15px]" onClick={onStartSession} disabled={busy}>
                <Play className="h-4 w-4 fill-current" aria-hidden="true" />
                Démarrer une session
              </Button>
            )
          )}
          {(book.status === "tbr" || book.status === "on_hold") && (
            <Button
              variant="outline"
              size="lg"
              className="h-11 rounded-[3px] px-5 text-[15px]"
              onClick={onMarkReading}
              disabled={busy}
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
              onClick={onTogglePrimary}
              disabled={busy}
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
              onClick={onMarkRead}
              disabled={busy}
            >
              <Check className="h-4 w-4" aria-hidden="true" />
              Marquer comme lu
            </Button>
          )}
        </div>

        {error && (
          <p className="text-[12.5px] text-ink-soft" role="alert">
            {error}
          </p>
        )}
      </div>
    </div>
  )
}
