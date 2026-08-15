import type { Author, Book, CurrentlyReading, Label, NavItem } from "@/types/book"

/**
 * Données statiques pour peupler l'interface le temps que frontend-dev
 * branche les vrais appels à /api/v1/books, /api/v1/authors et
 * /api/v1/labels. Rien ici n'appelle le réseau : les couvertures sont
 * des SVG générés localement (public/covers/mock/), pas des hotlinks.
 */

export const NAV_ITEMS: NavItem[] = [
  { key: "library", label: "Bibliothèque", href: "/" },
  { key: "tbr", label: "Pile à lire", href: "/pile-a-lire" },
  { key: "add", label: "Ajouter", href: "/ajouter" },
  { key: "stats", label: "Stats", href: "/stats" },
  { key: "settings", label: "Réglages", href: "/reglages" },
]

const authorPool: Author[] = [
  { id: 1, name: "M. Auber" },
  { id: 2, name: "C. Lindqvist" },
  { id: 3, name: "S. Rocher" },
  { id: 4, name: "T. Havel" },
  { id: 5, name: "N. Ferrant" },
  { id: 6, name: "J. Solberg" },
  { id: 7, name: "A. Coutin" },
  { id: 8, name: "E. Marbeuf" },
  { id: 9, name: "R. Ostrander" },
  { id: 10, name: "L. Peyrat" },
  { id: 11, name: "H. Grenon" },
  { id: 12, name: "D. Ashworth" },
  { id: 13, name: "P. Icart" },
  { id: 14, name: "V. Sundqvist" },
  { id: 15, name: "K. Norell" },
  { id: 16, name: "F. Delombre" },
  { id: 17, name: "B. Achterberg" },
  { id: 18, name: "O. Marchetti" },
]

const genrePool: Label[] = [
  { id: 1, name: "Roman", kind: "genre" },
  { id: 2, name: "Essai", kind: "genre" },
  { id: 3, name: "Nouvelles", kind: "genre" },
  { id: 4, name: "Science-fiction", kind: "genre" },
  { id: 5, name: "Poésie", kind: "genre" },
  { id: 6, name: "Récit", kind: "genre" },
]

const tagPool: Label[] = [
  { id: 101, name: "traduit", kind: "tag" },
  { id: 102, name: "premier roman", kind: "tag" },
  { id: 103, name: "prix littéraire", kind: "tag" },
  { id: 104, name: "relecture", kind: "tag" },
  { id: 105, name: "audio", kind: "tag" },
  { id: 106, name: "emprunté", kind: "tag" },
]

const titles = [
  "La Traversée lente",
  "Notes d'hiver",
  "Le Silence utile",
  "Cartographie du doute",
  "Trois saisons ailleurs",
  "L'Heure creuse",
  "Journal d'un passage",
  "Les Marges blanches",
  "Filature",
  "Ce que la mer efface",
  "Petit traité d'attente",
  "La Chambre commune",
  "Vers l'intérieur des terres",
  "Un hiver à part",
  "Le Bruit des pages",
  "Sous la latitude nord",
  "Récit du dernier étage",
  "Fragments de veille",
]

const statuses: Book["status"][] = [
  "reading",
  "tbr",
  "read",
  "read",
  "tbr",
  "reading",
  "read",
  "on_hold",
  "tbr",
  "read",
  "wishlist",
  "read",
  "dnf",
  "tbr",
  "read",
  "reading",
  "tbr",
  "read",
]

function pick<T>(pool: T[], seed: number, count: number): T[] {
  const out: T[] = []
  for (let i = 0; i < count; i++) {
    out.push(pool[(seed + i * 3) % pool.length])
  }
  return out
}

export const BOOKS: Book[] = titles.map((title, i) => {
  const n = String(i + 1).padStart(2, "0")
  const pageCount = 180 + ((i * 47) % 340)
  const status = statuses[i]
  const currentPercent =
    status === "reading"
      ? 0.12 + ((i * 0.17) % 0.7)
      : status === "read"
        ? 1
        : 0
  return {
    id: i + 1,
    title,
    subtitle: i % 5 === 0 ? "récit" : null,
    authors: [authorPool[i]],
    labels: [
      ...pick(genrePool, i, 1),
      ...pick(tagPool, i * 2, i % 3 === 0 ? 2 : 1),
    ],
    status,
    coverUrl: `/covers/mock/cover-${n}.svg`,
    pageCount,
    currentPage: Math.round(pageCount * currentPercent),
    currentPercent,
    rating: status === "read" ? [3, 3.5, 4, 4.5, 5][i % 5] : null,
  }
})

export const AUTHORS = authorPool
export const GENRES = genrePool
export const TAGS = tagPool

export const CURRENTLY_READING: CurrentlyReading = {
  book: BOOKS.find((b) => b.status === "reading") ?? BOOKS[0],
  lastSessionDurationSec: 32 * 60 + 15,
  sessionCount: 7,
}

export const STATUS_LABELS: Record<Book["status"], string> = {
  wishlist: "Wishlist",
  tbr: "À lire",
  reading: "En cours",
  read: "Lu",
  dnf: "Abandonné",
  on_hold: "En pause",
}
