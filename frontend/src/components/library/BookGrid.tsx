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
 *   >= 1200px ET pointer: coarse : auto-fill, min 132px (rail tactile)
 *   >= 1200px ET pointer: fine   : 7 colonnes fixes (desktop souris)
 *
 * Le palier desktop large (retour terrain de Jordy, 16/08/2026) fixe le
 * NOMBRE de colonnes plutôt que la taille mini de `auto-fill` : au-delà de
 * 1200px, `auto-fill`/`minmax` continue d'ajouter des colonnes de 118px
 * quand la fenêtre s'élargit, ce qui garde les pochettes petites sur un
 * grand écran. `grid-cols-7` fait l'inverse — le nombre de colonnes est
 * plafonné, ce sont les pochettes qui grandissent avec l'espace
 * disponible. Réservé à `pointer: fine` : le rail tactile (`pointer:
 * coarse`) garde sa formule `auto-fill` existante, layout différent
 * (rail + carte 300px, cf. AGENTS.md « Layouts »).
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
        pointer-coarse:@min-[1200px]:grid-cols-[repeat(auto-fill,minmax(132px,1fr))]
        pointer-fine:@min-[1200px]:grid-cols-7 pointer-fine:@min-[1200px]:gap-x-5 pointer-fine:@min-[1200px]:gap-y-10"
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
