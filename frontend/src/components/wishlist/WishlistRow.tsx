import { formatAuthors } from "@/lib/format"
import type { Book } from "@/types/book"

interface WishlistRowProps {
  book: Book
}

/**
 * Ligne de wishlist. Aucune couverture : un livre souhaité mais non
 * possédé n'a pas d'image locale à servir (AGENTS.md interdit le hotlink),
 * donc l'écran assume le typographique plutôt que de faire semblant avec
 * un placeholder d'image. C'est l'un des écrans "sans couverture" où la
 * hiérarchie tient au poids et à l'espacement.
 */
export function WishlistRow({ book }: WishlistRowProps) {
  return (
    <li className="flex items-center justify-between gap-4 border-b border-line-2 py-4 first:pt-0 last:border-b-0">
      <div className="min-w-0">
        <h3 className="truncate text-[15px] font-medium text-ink">{book.title}</h3>
        <p className="mt-0.5 truncate text-[13px] text-ink-mute">{formatAuthors(book.authors)}</p>
        {[...book.genres, ...book.tags].length > 0 && (
          <p className="mt-1 truncate text-[11px] uppercase tracking-[0.1em] text-ink-mute">
            {[...book.genres, ...book.tags].join(" · ")}
          </p>
        )}
      </div>

      <button
        type="button"
        className="min-h-11 shrink-0 rounded-[3px] border border-line px-3 text-[13px] text-ink-soft transition-colors hover:border-ink hover:text-ink"
      >
        Marquer comme acquis
      </button>
    </li>
  )
}
