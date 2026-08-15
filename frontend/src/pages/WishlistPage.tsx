import { listBooks } from "@/lib/api"
import { useBooks } from "@/context/books"
import { useAsyncData } from "@/lib/hooks"
import { WishlistRow } from "@/components/wishlist/WishlistRow"
import { WishlistEmptyState } from "@/components/wishlist/WishlistEmptyState"

/**
 * Wishlist — livres souhaités, non possédés (status="wishlist", owned=0).
 * GET /books?status=wishlist. Volontairement sans couverture,
 * cf. WishlistRow.tsx.
 */
export function WishlistPage() {
  const { booksVersion } = useBooks()
  const { data, error, loading, reload } = useAsyncData(
    () => listBooks({ status: "wishlist", page_size: 100 }),
    [booksVersion],
  )

  const books = data?.items ?? []

  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Wishlist
        </h1>
        {!loading && books.length > 0 && (
          <span className="text-[12.5px] tabular-nums text-ink-mute">
            {books.length} livre{books.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

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
      ) : loading ? null : books.length === 0 ? (
        <WishlistEmptyState />
      ) : (
        <ul>
          {books.map((book) => (
            <WishlistRow key={book.id} book={book} />
          ))}
        </ul>
      )}
    </div>
  )
}
