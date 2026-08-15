import { WISHLIST_BOOKS } from "@/lib/mock-data"
import { WishlistRow } from "@/components/wishlist/WishlistRow"
import { WishlistEmptyState } from "@/components/wishlist/WishlistEmptyState"
import type { Book } from "@/types/book"

interface WishlistPageProps {
  /**
   * Optionnel : par défaut WISHLIST_BOOKS (mock). Le harnais de QA visuelle
   * (App.tsx) passe un tableau vide pour visiter l'état vide sans dupliquer
   * la page — pas une vraie logique métier, juste un point d'entrée mock.
   */
  books?: Book[]
}

/**
 * Wishlist — livres souhaités, non possédés (status="wishlist", owned=0).
 * Données statiques — frontend-dev remplace par GET /books?status=wishlist.
 * Volontairement sans couverture, cf. WishlistRow.tsx.
 */
export function WishlistPage({ books = WISHLIST_BOOKS }: WishlistPageProps) {
  return (
    <div className="flex max-w-2xl flex-col gap-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          Wishlist
        </h1>
        {books.length > 0 && (
          <span className="text-[12.5px] tabular-nums text-ink-mute">
            {books.length} livre{books.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {books.length === 0 ? (
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
