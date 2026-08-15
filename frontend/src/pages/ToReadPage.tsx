import { CURRENTLY_READING, TBR_BOOKS } from "@/lib/mock-data"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { ToReadRow } from "@/components/tbr/ToReadRow"

/**
 * Pile à lire = "la sélection" : une liste curatée à la main, ordonnée
 * (mock-data.ts, `tbrRank`) — distincte du simple filtre `status==="tbr"`
 * de la Bibliothèque, qui reste un sous-ensemble non ordonné. TBR_BOOKS
 * est déjà trié par `tbrRank` (mock-data.ts) ; frontend-dev remplace par
 * GET /books?status=tbr&sort=tbr_rank sans toucher au balisage. Liste, pas
 * de grille : voir la note dans ToReadRow.tsx.
 */
export function ToReadPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="@min-[700px]:hidden">
        <CurrentlyReadingCard data={CURRENTLY_READING} variant="banner" />
      </div>

      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
            La sélection
          </p>
          <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
            Pile à lire
          </h1>
        </div>
        <span className="text-[12.5px] tabular-nums text-ink-mute">
          {TBR_BOOKS.length} livre{TBR_BOOKS.length > 1 ? "s" : ""}
        </span>
      </div>

      {TBR_BOOKS.length === 0 ? (
        <p className="py-16 text-center text-[15px] text-ink-mute">
          Rien en attente — la bibliothèque est à jour.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-line-2">
          {TBR_BOOKS.map((book, i) => (
            <li key={book.id}>
              <ToReadRow book={book} position={i + 1} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
