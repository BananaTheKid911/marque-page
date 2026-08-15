import { useState } from "react"
import { getStatsByAuthor, getStatsByGenre, getStatsOverview, getStatsTimeline } from "@/lib/api"
import { useAsyncData } from "@/lib/hooks"
import { StatsOverviewGrid } from "@/components/stats/StatsOverviewGrid"
import { StatsTimelineChart } from "@/components/stats/StatsTimelineChart"
import { StatsBreakdownList } from "@/components/stats/StatsBreakdownList"
import type { StatsRange } from "@/types/stats"

/**
 * Écran Statistiques — GET /stats/overview, /stats/timeline, /stats/by-genre,
 * /stats/by-author (backend/app/routers/stats.py). Formes snake_case telles
 * que servies par le backend (types/stats.ts), pas de mapper : le contrat
 * est déjà en snake_case des deux côtés.
 *
 * Composition (AGENTS.md) : un chiffre à 34px (streak) domine par la
 * taille, jamais par la couleur ; le graphique et les répartitions
 * n'utilisent qu'un ton d'encre, variations d'opacité/hauteur pour porter
 * la valeur. Aucune masse noire ici — pas de bouton d'action primaire sur
 * cet écran, la lecture seule ne réclame pas de point de fixation.
 */
export function StatsPage() {
  const [range, setRange] = useState<StatsRange>("day")

  const overviewData = useAsyncData(getStatsOverview, [])
  const timelineData = useAsyncData(() => getStatsTimeline(range), [range])
  const genreData = useAsyncData(getStatsByGenre, [])
  const authorData = useAsyncData(getStatsByAuthor, [])

  const hasError = overviewData.error || timelineData.error || genreData.error || authorData.error

  if (hasError) {
    const err = overviewData.error ?? timelineData.error ?? genreData.error ?? authorData.error
    return (
      <div className="flex flex-col gap-6">
        <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Statistiques
        </h1>
        <div className="flex flex-col items-start gap-3 rounded-[4px] border border-line bg-card p-4">
          <p className="text-[13.5px] text-ink-soft">
            Chargement impossible : {err instanceof Error ? err.message : String(err)}
          </p>
          <button
            type="button"
            onClick={() => {
              overviewData.reload()
              timelineData.reload()
              genreData.reload()
              authorData.reload()
            }}
            className="rounded-[3px] border border-ink px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-card"
          >
            Réessayer
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8 pb-8">
      <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
        Statistiques
      </h1>

      <StatsOverviewGrid overview={overviewData.data} loading={overviewData.loading} />

      <StatsTimelineChart
        points={timelineData.data?.points ?? []}
        range={range}
        onRangeChange={setRange}
        loading={timelineData.loading}
      />

      <div className="flex flex-col gap-8 @min-[700px]:grid @min-[700px]:grid-cols-2 @min-[700px]:gap-x-8 @min-[700px]:gap-y-0">
        <StatsBreakdownList
          title="Par genre"
          items={genreData.data?.items ?? []}
          loading={genreData.loading}
          emptyLabel="Pas encore de genre renseigné sur tes sessions."
        />
        <StatsBreakdownList
          title="Par auteur"
          items={authorData.data?.items ?? []}
          loading={authorData.loading}
          emptyLabel="Pas encore de session enregistrée."
        />
      </div>
    </div>
  )
}
