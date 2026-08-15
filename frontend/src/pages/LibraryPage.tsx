import { AUTHORS, BOOKS, CURRENTLY_READING, GENRES, SERIES, TAGS } from "@/lib/mock-data"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { LibraryFilters } from "@/components/library/LibraryFilters"
import { BookGrid } from "@/components/library/BookGrid"

interface LibraryPageProps {
  /**
   * Optionnel : série active, portée par la QA route `?serie=<id>` (voir
   * App.tsx) — pas une vraie logique de filtrage (frontend-dev la
   * branchera), juste un point d'entrée pour visiter/vérifier visuellement
   * le comportement "tri par tome" décrit dans AGENTS.md/le brief produit.
   */
  seriesFilterId?: number
}

/**
 * Vue Bibliothèque. Données statiques (BOOKS, AUTHORS, GENRES, TAGS) —
 * frontend-dev remplace ces imports par les résultats de
 * GET /api/v1/books, /authors, /labels sans toucher au balisage.
 *
 * Choisir une série n'est PAS un filtre comme les autres : au lieu de
 * réduire la liste sans changer son ordre, il réordonne par numéro de
 * tome et fait apparaître un badge "T. X" sur chaque couverture — la
 * grille change de comportement, pas seulement de contenu.
 */
export function LibraryPage({ seriesFilterId }: LibraryPageProps) {
  const activeSeries = seriesFilterId != null ? SERIES.find((s) => s.id === seriesFilterId) : undefined

  const books = activeSeries
    ? BOOKS.filter((b) => b.seriesId === activeSeries.id).sort(
        (a, b) => (a.seriesIndex ?? 0) - (b.seriesIndex ?? 0),
      )
    : BOOKS

  return (
    <div className="flex flex-col gap-6">
      <div className="@min-[700px]:hidden">
        <CurrentlyReadingCard data={CURRENTLY_READING} variant="banner" />
      </div>

      <div className="flex items-baseline justify-between">
        <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Bibliothèque
        </h1>
        <span className="text-[12.5px] tabular-nums text-ink-mute">
          {books.length} livre{books.length > 1 ? "s" : ""}
        </span>
      </div>

      <LibraryFilters
        authors={AUTHORS}
        genres={GENRES}
        tags={TAGS}
        series={SERIES}
        activeStatus="all"
        activeSeriesId={activeSeries ? activeSeries.id : "all"}
      />

      {activeSeries && (
        <p className="text-[12.5px] text-ink-mute">
          Triée par tome — <span className="font-medium text-ink">{activeSeries.name}</span>
        </p>
      )}

      <BookGrid books={books} seriesMode={Boolean(activeSeries)} />
    </div>
  )
}
