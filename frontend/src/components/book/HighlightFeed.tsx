import { Badge } from "@/components/ui/badge"
import { formatDate } from "@/lib/format"
import type { Highlight } from "@/types/book"

interface HighlightFeedProps {
  highlights: Highlight[]
}

const SOURCE_LABELS: Record<Highlight["source"], string> = {
  manual: "manuel",
  koreader: "KOReader",
}

/**
 * Highlights associés au livre. Citation en serif italique (le texte lui-
 * même porte la hiérarchie), métadonnées en petites capitales — aucune
 * couleur pour distinguer la source manuel/KOReader, juste un badge outline.
 */
export function HighlightFeed({ highlights }: HighlightFeedProps) {
  return (
    <section aria-label="Highlights">
      <h2 className="text-[15px] font-semibold text-ink">Highlights</h2>

      {highlights.length === 0 ? (
        <p className="mt-3 text-[13.5px] text-ink-mute">
          Aucun highlight pour ce livre.
        </p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {highlights.map((highlight) => (
            <li
              key={highlight.id}
              className="rounded-[4px] border-l-2 border-line bg-card p-4 shadow-card"
            >
              <p className="text-[15px] leading-relaxed text-ink italic">
                “{highlight.text}”
              </p>
              {highlight.note && (
                <p className="mt-2 text-[13px] text-ink-soft">{highlight.note}</p>
              )}
              <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] uppercase tracking-[0.12em] text-ink-mute">
                {highlight.chapter && <span>{highlight.chapter}</span>}
                {highlight.page != null && <span className="tabular-nums">p. {highlight.page}</span>}
                <span>{formatDate(highlight.highlightedAt)}</span>
                <Badge variant="outline" className="text-[10px] font-normal normal-case tracking-normal text-ink-mute">
                  {SOURCE_LABELS[highlight.source]}
                </Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
