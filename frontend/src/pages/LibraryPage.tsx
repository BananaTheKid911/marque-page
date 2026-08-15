import { AUTHORS, BOOKS, CURRENTLY_READING, GENRES, TAGS } from "@/lib/mock-data"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { LibraryFilters } from "@/components/library/LibraryFilters"
import { BookGrid } from "@/components/library/BookGrid"

/**
 * Vue Bibliothèque. Données statiques (BOOKS, AUTHORS, GENRES, TAGS) —
 * frontend-dev remplace ces imports par les résultats de
 * GET /api/v1/books, /authors, /labels sans toucher au balisage.
 */
export function LibraryPage() {
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
          {BOOKS.length} livres
        </span>
      </div>

      <LibraryFilters
        authors={AUTHORS}
        genres={GENRES}
        tags={TAGS}
        activeStatus="all"
      />

      <BookGrid books={BOOKS} />
    </div>
  )
}
