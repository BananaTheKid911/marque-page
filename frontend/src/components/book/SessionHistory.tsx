import { formatDate, formatDuration } from "@/lib/format"
import type { ReadingSession } from "@/types/book"

interface SessionHistoryProps {
  sessions: ReadingSession[]
}

const SOURCE_LABELS: Record<ReadingSession["source"], string> = {
  manual: "saisie manuelle",
  timer: "chrono",
  koreader: "KOReader",
}

/**
 * Historique des sessions de lecture. Liste, pas de tableau : plus lisible
 * en colonne étroite (mobile). Durée et pages en tabular-nums pour rester
 * alignées visuellement d'une ligne à l'autre.
 */
export function SessionHistory({ sessions }: SessionHistoryProps) {
  return (
    <section aria-label="Historique des sessions">
      <h2 className="text-[15px] font-semibold text-ink">Sessions</h2>

      {sessions.length === 0 ? (
        <p className="mt-3 text-[13.5px] text-ink-mute">
          Aucune session enregistrée pour ce livre.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col divide-y divide-line-2 rounded-[4px] border border-line">
          {sessions.map((session) => (
            <li
              key={session.id}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
              <div className="min-w-0">
                <p className="text-[13.5px] text-ink">{formatDate(session.startedAt)}</p>
                <p className="mt-0.5 text-[11px] uppercase tracking-[0.12em] text-ink-mute">
                  {SOURCE_LABELS[session.source]}
                </p>
              </div>
              <div className="flex shrink-0 items-baseline gap-4 text-[13px] tabular-nums text-ink-soft">
                {session.pagesRead != null && <span>{session.pagesRead} p.</span>}
                <span className="font-medium text-ink">
                  {formatDuration(session.durationSec)}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
