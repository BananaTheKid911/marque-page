import { useEffect, useState } from "react"
import { useSearchParams } from "react-router-dom"
import {
  listAuthors,
  listBooks,
  listLabels,
  listSeries,
  listSeriesBooks,
} from "@/lib/api"
import { useBooks } from "@/context/books"
import { useAsyncData } from "@/lib/hooks"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { LibraryFilters, type LibraryFilterState } from "@/components/library/LibraryFilters"
import { BookGrid } from "@/components/library/BookGrid"
import type { Book, BookList, SeriesBooks } from "@/types/book"

const DEFAULT_FILTERS: LibraryFilterState = {
  status: "all",
  seriesId: "all",
  q: "",
  authorId: "all",
  genreId: "all",
  tagId: "all",
}

type BooksResult = { kind: "list"; data: BookList } | { kind: "series"; data: SeriesBooks }

/**
 * Vue Bibliothèque — alimentée par GET /books (filtres réels : status,
 * `q`, auteur, genre, tag) et GET /series/{id}/books pour le mode série
 * (tri par tome + badges). La série active est portée par l'URL (`?serie=`)
 * : elle change le comportement de la grille, pas juste son contenu.
 *
 * Pagination : page_size=100 sans UI de pagination pour ce lot — au-delà,
 * la grille n'affiche que les 100 premiers (à dessiner avec design-ui).
 */
export function LibraryPage() {
  const { currentlyReading, booksVersion } = useBooks()
  const [searchParams, setSearchParams] = useSearchParams()

  const serieParam = searchParams.get("serie")
  const seriesId: number | "all" = serieParam ? Number(serieParam) : "all"

  const [filters, setFilters] = useState<Omit<LibraryFilterState, "seriesId">>({
    status: DEFAULT_FILTERS.status,
    q: DEFAULT_FILTERS.q,
    authorId: DEFAULT_FILTERS.authorId,
    genreId: DEFAULT_FILTERS.genreId,
    tagId: DEFAULT_FILTERS.tagId,
  })

  // Recherche débouncée (300 ms) : ne pas marteler l'API à chaque frappe.
  const [debouncedQ, setDebouncedQ] = useState(filters.q.trim())
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQ(filters.q.trim()), 300)
    return () => clearTimeout(timer)
  }, [filters.q])

  // Taxonomie pour les filtres — chargée une fois.
  const authors = useAsyncData(listAuthors, [])
  const genres = useAsyncData(() => listLabels("genre"), [])
  const tags = useAsyncData(() => listLabels("tag"), [])
  const series = useAsyncData(listSeries, [])

  const seriesMode = seriesId !== "all"
  const activeSeriesId = seriesMode ? (seriesId as number) : null

  const authorName =
    filters.authorId === "all"
      ? undefined
      : authors.data?.find((a) => a.id === filters.authorId)?.name
  const genreName =
    filters.genreId === "all" ? undefined : genres.data?.items.find((g) => g.id === filters.genreId)?.name
  const tagName =
    filters.tagId === "all" ? undefined : tags.data?.items.find((t) => t.id === filters.tagId)?.name

  const booksQuery = (): Promise<BooksResult> =>
    seriesMode
      ? listSeriesBooks(activeSeriesId as number).then((sb) => ({
          kind: "series" as const,
          data: sb,
        }))
      : listBooks({
          status: filters.status === "all" ? undefined : filters.status,
          q: debouncedQ || undefined,
          author: authorName,
          genre: genreName,
          tag: tagName,
          page_size: 100,
        }).then((lb) => ({ kind: "list" as const, data: lb }))
  const { data, error, loading, reload } = useAsyncData(booksQuery, [
    seriesMode,
    activeSeriesId,
    filters.status,
    debouncedQ,
    authorName,
    genreName,
    tagName,
    booksVersion,
  ])

  const books: Book[] = data ? (data.kind === "list" ? data.data.items : data.data.books) : []
  const total = data ? (data.kind === "list" ? data.data.total : data.data.books.length) : 0
  const activeSeries = data?.kind === "series" ? data.data.series : null

  const onSeriesChange = (id: number | "all") => {
    const next = new URLSearchParams(searchParams)
    if (id === "all") next.delete("serie")
    else next.set("serie", String(id))
    setSearchParams(next, { replace: true })
  }

  // Le `seriesId` vit dans l'URL (état de navigation), pas dans les filtres
  // locaux : on le route séparément du reste du patch.
  const handleFiltersChange = (patch: Partial<LibraryFilterState>) => {
    const { seriesId: nextSeries, ...rest } = patch
    if (Object.keys(rest).length > 0) setFilters((f) => ({ ...f, ...rest }))
    if (nextSeries !== undefined) onSeriesChange(nextSeries)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="@min-[700px]:hidden">
        <CurrentlyReadingCard data={currentlyReading} variant="banner" />
      </div>

      <div className="flex items-baseline justify-between">
        <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Bibliothèque
        </h1>
        {!loading && (
          <span className="text-[12.5px] tabular-nums text-ink-mute">
            {total} livre{total > 1 ? "s" : ""}
          </span>
        )}
      </div>

      <LibraryFilters
        authors={authors.data ?? []}
        genres={genres.data?.items ?? []}
        tags={tags.data?.items ?? []}
        series={series.data ?? []}
        filters={{ ...filters, seriesId }}
        onChange={handleFiltersChange}
      />

      {seriesMode && activeSeries && (
        <p className="text-[12.5px] text-ink-mute">
          Triée par tome — <span className="font-medium text-ink">{activeSeries.name}</span>
        </p>
      )}

      {error ? (
        <div className="flex flex-col items-start gap-3 rounded-[4px] border border-line bg-card p-4">
          <p className="text-[13.5px] text-ink-soft">
            Chargement impossible : {error instanceof Error ? error.message : String(error)}
          </p>
          <button
            type="button"
            onClick={reload}
            className="rounded-[3px] border border-ink px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-card"
          >
            Réessayer
          </button>
        </div>
      ) : (
        <BookGrid books={books} seriesMode={seriesMode} />
      )}
    </div>
  )
}
