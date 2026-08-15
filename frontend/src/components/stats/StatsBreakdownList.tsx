import { formatDuration } from "@/lib/format"
import type { BreakdownItem } from "@/types/stats"

interface StatsBreakdownListProps {
  title: string
  items: BreakdownItem[]
  loading: boolean
  emptyLabel: string
}

const MAX_VISIBLE = 8

/**
 * Répartition genre/auteur — classement par durée décroissante (déjà trié
 * côté backend). Une barre discrète sous chaque ligne porte la valeur
 * relative au premier de la liste ; aucune couleur, un seul ton d'encre.
 * Composant générique : StatsPage l'instancie deux fois (genre, auteur).
 */
export function StatsBreakdownList({ title, items, loading, emptyLabel }: StatsBreakdownListProps) {
  const visible = items.slice(0, MAX_VISIBLE)
  const max = Math.max(1, ...visible.map((i) => i.duration_sec))

  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h2 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">{title}</h2>

      {loading ? (
        <div className="flex flex-col gap-2.5">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-[42px] animate-pulse rounded-[4px] bg-card shadow-card" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <p className="rounded-[4px] border border-line-2 bg-card px-4 py-6 text-center text-[13.5px] text-ink-mute shadow-card">
          {emptyLabel}
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {visible.map((item, index) => {
            const pct = Math.max((item.duration_sec / max) * 100, item.duration_sec > 0 ? 3 : 0)
            return (
              <li key={item.label} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0 truncate text-[15px] text-ink">
                    <span className="mr-2 tabular-nums text-ink-mute">{index + 1}.</span>
                    {item.label}
                  </span>
                  <span className="shrink-0 tabular-nums text-[12.5px] text-ink-mute">
                    {formatDuration(item.duration_sec)}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-line-2">
                  <div className="h-full rounded-full bg-ink" style={{ width: `${pct}%` }} />
                </div>
              </li>
            )
          })}
        </ol>
      )}

      {!loading && items.length > MAX_VISIBLE && (
        <p className="text-[12px] text-ink-mute">+ {items.length - MAX_VISIBLE} autres</p>
      )}
    </section>
  )
}
