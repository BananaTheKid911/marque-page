import { Clock } from "lucide-react"
import { cn } from "@/lib/utils"
import { formatDuration } from "@/lib/format"
import type { StatsRange, TimelinePoint } from "@/types/stats"

interface StatsTimelineChartProps {
  points: TimelinePoint[]
  range: StatsRange
  onRangeChange: (range: StatsRange) => void
  loading: boolean
}

const RANGE_OPTIONS: { key: StatsRange; label: string }[] = [
  { key: "day", label: "Jour" },
  { key: "week", label: "Semaine" },
  { key: "month", label: "Mois" },
]

const monthFormatter = new Intl.DateTimeFormat("fr-FR", { month: "short" })

/** Étiquette courte sous chaque barre — jamais la date ISO brute. */
function periodLabel(period: string, range: StatsRange): string {
  if (range === "day") {
    return String(Number(period.slice(8, 10)))
  }
  if (range === "week") {
    return `S${period.slice(6)}`
  }
  const [year, month] = period.split("-")
  return monthFormatter.format(new Date(Number(year), Number(month) - 1, 1))
}

const BAR_HEIGHT_PX = 108

/**
 * Timeline en barres — pas de librairie de charts : des `div` dont la
 * hauteur porte la valeur et l'opacité porte la récence (la barre la plus
 * récente est pleine encre, les plus anciennes s'estompent). Un seul ton
 * (`bg-ink`), conforme à AGENTS.md — jamais de couleur pour distinguer
 * les barres entre elles.
 */
export function StatsTimelineChart({ points, range, onRangeChange, loading }: StatsTimelineChartProps) {
  const total = points.reduce((sum, p) => sum + p.duration_sec, 0)
  const max = Math.max(1, ...points.map((p) => p.duration_sec))

  return (
    <section aria-label="Historique de lecture" className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Historique
        </h2>
        {!loading && points.length > 0 && (
          <span className="text-[12.5px] tabular-nums text-ink-mute">
            {formatDuration(total)} au total
          </span>
        )}
      </div>

      <ul className="flex gap-5" role="tablist" aria-label="Période">
        {RANGE_OPTIONS.map(({ key, label }) => {
          const isActive = key === range
          return (
            <li key={key}>
              <button
                type="button"
                role="tab"
                aria-selected={isActive}
                onClick={() => onRangeChange(key)}
                className={cn(
                  "border-b-2 border-transparent py-2 text-[15px] transition-colors",
                  isActive ? "border-b-ink text-ink" : "text-ink-mute hover:text-ink",
                )}
              >
                {label}
              </button>
            </li>
          )
        })}
      </ul>

      {loading ? (
        <div
          className="animate-pulse rounded-[4px] bg-card shadow-card"
          style={{ height: BAR_HEIGHT_PX + 48 }}
        />
      ) : points.length === 0 || total === 0 ? (
        <EmptyTimeline />
      ) : (
        <div className="overflow-x-auto rounded-[4px] bg-card p-4 shadow-card">
          <div
            className="flex items-end gap-2"
            style={{ height: BAR_HEIGHT_PX, minWidth: points.length * 28 }}
          >
            {points.map((point, index) => {
              const heightRatio = point.duration_sec / max
              const recency = points.length > 1 ? index / (points.length - 1) : 1
              const opacity = point.duration_sec === 0 ? 0 : 0.32 + 0.68 * recency
              return (
                <div
                  key={point.period}
                  className="flex h-full w-5 shrink-0 flex-col items-center justify-end gap-1.5"
                  title={`${periodLabel(point.period, range)} — ${formatDuration(point.duration_sec)}, ${point.pages_read} page${point.pages_read > 1 ? "s" : ""}`}
                >
                  <div
                    className="flex w-full items-end overflow-hidden rounded-t-[2px] bg-line-2"
                    style={{ height: BAR_HEIGHT_PX }}
                  >
                    <div
                      className="w-full rounded-t-[2px] bg-ink"
                      style={{
                        height: `${Math.max(heightRatio * 100, point.duration_sec > 0 ? 4 : 0)}%`,
                        opacity,
                      }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
          <div className="mt-2 flex gap-2" style={{ minWidth: points.length * 28 }}>
            {points.map((point) => (
              <span
                key={point.period}
                className="w-5 shrink-0 text-center text-[10.5px] tabular-nums text-ink-mute"
              >
                {periodLabel(point.period, range)}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function EmptyTimeline() {
  return (
    <div className="flex flex-col items-center gap-2 rounded-[4px] border border-line-2 bg-card px-4 py-9 text-center shadow-card">
      <Clock className="h-6 w-6 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
      <p className="text-[13.5px] text-ink-mute">
        Pas encore de session enregistrée sur cette période.
      </p>
    </div>
  )
}
