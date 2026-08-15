import { formatTome } from "@/lib/format"
import type { Book } from "@/types/book"
import { BookCover } from "./BookCover"

interface BookGridProps {
  books: Book[]
  /**
   * Vrai quand `books` est déjà filtré+trié par série (LibraryPage).
   * Change uniquement l'affichage (badge "T. X" par couverture) — le tri
   * lui-même est la responsabilité de l'appelant, pas de ce composant.
   */
  seriesMode?: boolean
}

/**
 * Grille de couvertures. Colonnes pilotées par @container, sur le même
 * conteneur racine que la nav (AGENTS.md : "un seul jeu de règles") —
 * pas de requête indépendante ici, mêmes seuils que le shell :
 *
 *   < 700px                      : 3 colonnes fixes
 *   >= 700px                     : auto-fill, min 118px
 *   >= 1200px ET pointer: coarse : auto-fill, min 132px
 */
export function BookGrid({ books, seriesMode = false }: BookGridProps) {
  if (books.length === 0) {
    return (
      <p className="py-16 text-center text-[15px] text-ink-mute">
        Aucun livre ne correspond à ces filtres.
      </p>
    )
  }

  return (
    <ul
      className="grid grid-cols-3 gap-x-3 gap-y-6
        @min-[700px]:grid-cols-[repeat(auto-fill,minmax(118px,1fr))] @min-[700px]:gap-x-4 @min-[700px]:gap-y-8
        pointer-coarse:@min-[1200px]:grid-cols-[repeat(auto-fill,minmax(132px,1fr))]"
    >
      {books.map((book) => (
        <li key={book.id}>
          <BookCover
            book={book}
            tomeLabel={
              seriesMode && book.seriesIndex != null
                ? `T. ${formatTome(book.seriesIndex)}`
                : undefined
            }
          />
        </li>
      ))}
    </ul>
  )
}
