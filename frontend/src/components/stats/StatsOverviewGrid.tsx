import { formatDuration } from "@/lib/format"
import type { StatsOverview } from "@/types/stats"

interface StatsOverviewGridProps {
  overview: StatsOverview | null
  loading: boolean
}

const SKELETON_TILES = [0, 1, 2]

/**
 * Bloc "overview" — la série de lecture (streak) porte le chiffre à 34px
 * (AGENTS.md « échelle typographique »), seule masse qui domine par la
 * taille sur cet écran. Les trois tuiles secondaires (temps, pages, note)
 * partagent un même gabarit à 22px : elles informent, elles ne rivalisent
 * pas avec le streak.
 */
export function StatsOverviewGrid({ overview, loading }: StatsOverviewGridProps) {
  if (loading || !overview) {
    return (
      <div className="flex flex-col gap-3">
        <div className="h-[132px] animate-pulse rounded-[4px] bg-card shadow-card" />
        <div className="grid grid-cols-3 gap-2 @min-[700px]:gap-3">
          {SKELETON_TILES.map((i) => (
            <div key={i} className="h-[74px] animate-pulse rounded-[4px] bg-card shadow-card" />
          ))}
        </div>
      </div>
    )
  }

  const hasSessions = overview.total_sessions > 0
  const streakCaption = hasSessions
    ? `jour${overview.streak_days > 1 ? "s" : ""} consécutif${overview.streak_days > 1 ? "s" : ""}`
    : "Commence une session pour démarrer une série"

  return (
    <div className="flex flex-col gap-3">
      <section aria-label="Série de lecture" className="rounded-[4px] bg-card p-5 shadow-card">
        <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">
          Série de lecture
        </p>
        <div className="mt-2 flex items-baseline gap-2.5">
          <span className="text-[34px] font-semibold leading-none tabular-nums text-ink">
            {overview.streak_days}
          </span>
          <span className="text-[13.5px] text-ink-mute">{streakCaption}</span>
        </div>
        <dl className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-ink-mute">
          <div>
            <dt className="inline">Possédés </dt>
            <dd className="inline tabular-nums text-ink-soft">{overview.books_owned}</dd>
          </div>
          <div>
            <dt className="inline">Lus </dt>
            <dd className="inline tabular-nums text-ink-soft">{overview.books_read}</dd>
          </div>
          <div>
            <dt className="inline">En cours </dt>
            <dd className="inline tabular-nums text-ink-soft">{overview.books_reading}</dd>
          </div>
          <div>
            <dt className="inline">À lire </dt>
            <dd className="inline tabular-nums text-ink-soft">{overview.books_tbr}</dd>
          </div>
        </dl>
      </section>

      <div className="grid grid-cols-3 gap-2 @min-[700px]:gap-3">
        <StatTile label="Temps total" value={formatDuration(overview.total_duration_sec)} />
        <StatTile
          label="Pages lues"
          value={overview.total_pages_read.toLocaleString("fr-FR")}
        />
        <StatTile
          label="Note moyenne"
          value={
            overview.avg_rating != null
              ? overview.avg_rating.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })
              : "—"
          }
          hint={overview.avg_rating != null ? "/ 5" : "Aucune note"}
        />
      </div>
    </div>
  )
}

function StatTile({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-[4px] bg-card p-3.5 shadow-card @min-[700px]:p-4">
      <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute">{label}</p>
      <p className="flex items-baseline gap-1 text-[19px] font-semibold tabular-nums text-ink @min-[1200px]:text-[22px]">
        {value}
        {hint && <span className="text-[11px] font-normal text-ink-mute">{hint}</span>}
      </p>
    </div>
  )
}
