import type { ReactNode } from "react"
import { formatAuthors, formatDuration } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { KoreaderBookPreview } from "@/types/koreader"

interface KoreaderMatchCardProps {
  book: KoreaderBookPreview
  /** `null` = "ignorer ce livre" sélectionné (ou rien encore choisi). */
  selectedBookId: number | null
  onSelect: (bookId: number | null) => void
}

/** Score → label lisible sans couleur (AGENTS.md : le poids et le texte
 * portent la hiérarchie, pas une pastille verte/orange/rouge). */
function scoreLabel(score: number): string {
  if (score >= 0.85) return "Correspondance forte"
  if (score >= 0.65) return "Correspondance probable"
  return "Correspondance faible"
}

/**
 * Un livre KOReader non rattaché automatiquement + ses candidats
 * (§4.3). Sélection en radio natif (pas de nouveau primitif shadcn à
 * installer) : chaque option est une ligne cliquable pleine cible
 * tactile, l'état sélectionné se voit à la bordure qui passe de
 * `--line` à `--ink` et à un point plein en encre — même levier que la
 * masse noire, réduit à l'échelle d'une ligne de formulaire.
 */
export function KoreaderMatchCard({ book, selectedBookId, onSelect }: KoreaderMatchCardProps) {
  const groupName = `koreader-match-${book.koreaderBookId}`

  return (
    <div className="rounded-[4px] border border-line bg-card">
      <div className="border-b border-line-2 px-4 py-3.5">
        <p className="text-[14.5px] text-ink">{book.title}</p>
        <p className="mt-0.5 text-[12.5px] text-ink-mute">
          {formatAuthors(book.authors)} · {book.totalSessions} session
          {book.totalSessions > 1 ? "s" : ""} · {formatDuration(book.totalDurationSec)}
        </p>
      </div>

      <fieldset className="flex flex-col">
        <legend className="sr-only">
          Rattachement suggéré pour « {book.title} »
        </legend>

        {book.candidates.length === 0 && (
          <p className="px-4 py-3 text-[13px] text-ink-mute">
            Aucun candidat trouvé dans la bibliothèque.
          </p>
        )}

        {book.candidates.map((candidate) => (
          <MatchOption
            key={candidate.bookId}
            name={groupName}
            checked={selectedBookId === candidate.bookId}
            onCheck={() => onSelect(candidate.bookId)}
          >
            <div className="min-w-0">
              <p className="truncate text-[13.5px] text-ink">{candidate.title}</p>
              <p className="mt-0.5 truncate text-[12px] text-ink-mute">
                {formatAuthors(candidate.authors)}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-[12px] text-ink-soft">{scoreLabel(candidate.score)}</p>
              <p className="mt-0.5 text-[11.5px] tabular-nums text-ink-mute">
                {Math.round(candidate.score * 100)} %
              </p>
            </div>
          </MatchOption>
        ))}

        <MatchOption
          name={groupName}
          checked={selectedBookId === null}
          onCheck={() => onSelect(null)}
        >
          <p className="text-[13.5px] text-ink-mute">Ignorer ce livre</p>
          <p className="text-[12px] text-ink-mute">Pas de rattachement</p>
        </MatchOption>
      </fieldset>
    </div>
  )
}

function MatchOption({
  name,
  checked,
  onCheck,
  children,
}: {
  name: string
  checked: boolean
  onCheck: () => void
  children: ReactNode
}) {
  return (
    <label
      className={cn(
        "flex min-h-[44px] cursor-pointer items-center justify-between gap-4 border-t border-line-2 px-4 py-3 transition-colors first:border-t-0 hover:bg-paper",
      )}
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onCheck}
        className="sr-only"
      />
      <span
        aria-hidden="true"
        className={cn(
          "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
          checked ? "border-ink" : "border-line",
        )}
      >
        {checked && <span className="h-2 w-2 rounded-full bg-ink" />}
      </span>
      <span className="flex min-w-0 flex-1 items-center justify-between gap-4">{children}</span>
    </label>
  )
}
