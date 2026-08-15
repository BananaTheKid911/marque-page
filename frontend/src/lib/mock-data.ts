import type {
  Author,
  Book,
  CurrentlyReading,
  Highlight,
  Label,
  NavItem,
  ReadingSession,
  Series,
} from "@/types/book"

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

/**
 * Jordy lit sur plusieurs supports en parallèle (Kindle/KOReader + papier) :
 * plusieurs livres peuvent être `status === "reading"` en même temps. Un
 * seul porte `isPrimaryReading = true` — c'est celui-là qui apparaît sur
 * la carte "En cours" (CurrentlyReadingCard). Le choix se fait à la main
 * depuis BookDetailPage (décision produit du 15/08/2026, cf. BookHero) ;
 * ici on fixe explicitement l'exclusivité pour le mock.
 */
const PRIMARY_READING_ID = 1

for (const book of BOOKS) {
  if (book.status === "reading") {
    book.isPrimaryReading = book.id === PRIMARY_READING_ID
  }
}

export const CURRENTLY_READING: CurrentlyReading = {
  book:
    BOOKS.find((b) => b.status === "reading" && b.isPrimaryReading) ??
    BOOKS.find((b) => b.status === "reading") ??
    BOOKS[0],
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

const publisherPool = [
  "Éditions du Sillage",
  "Cheval d'écume",
  "Presses de la Marge",
  "Atelier du Nord",
  "Verger noir",
]

const descriptionPool = [
  "Un roman qui avance par ellipses, où chaque chapitre referme une porte avant d'en ouvrir une autre. L'auteur y poursuit une réflexion entamée dans ses textes précédents sur la mémoire des lieux traversés.",
  "Récit à la première personne construit sur une année, saison après saison — l'ordinaire d'une vie observée avec une attention presque clinique, sans jamais verser dans la confession.",
  "Un texte bref et dense, salué à sa sortie pour la précision de sa langue. Peu d'action, beaucoup de silence : c'est dans les blancs que le livre se joue.",
]

/**
 * Enrichit quelques livres (celui en cours + deux "lus") avec les champs
 * utilisés par la page Détail, absents des mocks de grille. Le reste du
 * catalogue garde `description`/`publisher`/`year` à `null` : la page
 * Détail doit rester correcte même sans ces champs (backend réel).
 */
const detailSeedIds = new Set(
  [CURRENTLY_READING.book.id, ...BOOKS.filter((b) => b.status === "read").map((b) => b.id)].slice(
    0,
    5,
  ),
)

for (const book of BOOKS) {
  if (!detailSeedIds.has(book.id)) continue
  book.publisher = publisherPool[book.id % publisherPool.length]
  book.year = 2014 + (book.id % 11)
  book.description = descriptionPool[book.id % descriptionPool.length]
  if (book.status === "read") {
    book.startedAt = "2026-06-02T09:00:00"
    book.finishedAt = "2026-06-21T21:40:00"
  } else if (book.status === "reading") {
    book.startedAt = "2026-08-01T08:15:00"
  }
}

/**
 * Série mock — inspirée de la table `book.series` de KOReader (SPEC.md
 * §4.1), concept absent du schéma actuel. Une seule série pour l'instant,
 * 4 tomes dont un hors-série (index décimal 2.5), suffisant pour vérifier
 * le tri par tome et le badge sur couverture.
 */
export const SERIES: Series[] = [{ id: 1, name: "Les Cahiers de la Marge" }]

const SERIES_TOMES: Record<number, number> = {
  3: 1, // Le Silence utile
  4: 2, // Cartographie du doute
  7: 2.5, // Journal d'un passage — hors-série
  10: 3, // Ce que la mer efface
}

for (const book of BOOKS) {
  const index = SERIES_TOMES[book.id]
  if (index === undefined) continue
  book.seriesId = SERIES[0].id
  book.seriesIndex = index
}

/**
 * Format + possession — deux dimensions orthogonales au statut, absentes
 * du schéma actuel (SPEC.md ne modélise `owned` qu'au niveau du livre).
 * `owned` varie ici PAR format sur un même livre (id 7 : édition papier
 * empruntée, version numérique achetée) — cas réel de Jordy, pas un
 * exemple théorique. Prix/date d'achat restent uniques par livre.
 */
const FORMAT_SEEDS: Record<number, { formats: Book["formats"]; pricePaid?: number; purchasedAt?: string }> = {
  1: { formats: [{ type: "digital", owned: false }] }, // emprunté, en cours — pas d'achat
  3: {
    formats: [
      { type: "physique", owned: true },
      { type: "digital", owned: true },
    ],
    pricePaid: 19.9,
    purchasedAt: "2026-03-02T00:00:00",
  },
  4: {
    formats: [{ type: "physique", owned: true }],
    pricePaid: 21.5,
    purchasedAt: "2026-04-18T00:00:00",
  },
  6: {
    formats: [{ type: "digital", owned: true }],
    pricePaid: 9.99,
    purchasedAt: "2026-07-20T00:00:00",
  },
  7: {
    formats: [
      { type: "physique", owned: false },
      { type: "digital", owned: true },
    ],
    pricePaid: 12.9,
    purchasedAt: "2026-05-05T00:00:00",
  },
  10: {
    formats: [
      { type: "physique", owned: true },
      { type: "audio", owned: false },
    ],
    pricePaid: 24,
    purchasedAt: "2026-06-10T00:00:00",
  },
  16: {
    formats: [{ type: "physique", owned: true }],
    pricePaid: 18.5,
    purchasedAt: "2026-08-01T00:00:00",
  },
}

for (const book of BOOKS) {
  const seed = FORMAT_SEEDS[book.id]
  if (!seed) continue
  book.formats = seed.formats
  if (book.status !== "wishlist") {
    book.pricePaid = seed.pricePaid ?? null
    book.purchasedAt = seed.purchasedAt ?? null
  }
}

/** Série d'un livre, `null` s'il n'appartient à aucune série. */
export function seriesForBook(book: Book): Series | null {
  if (book.seriesId == null) return null
  return SERIES.find((s) => s.id === book.seriesId) ?? null
}

/**
 * Tous les tomes possédés d'une série (le livre courant inclus), triés
 * par numéro de tome croissant. "Possédés" = présents dans la
 * bibliothèque (donc `owned = 1` au sens SPEC.md §5, tout statut hors
 * wishlist) — pas une lecture stricte du champ `formats[].owned`, qui
 * répond à une question plus fine (par quel format). Si Jordy veut la
 * distinction plus fine ici aussi, c'est une question à lui remonter.
 */
export function seriesTomes(book: Book): Book[] {
  if (book.seriesId == null) return []
  return BOOKS.filter((b) => b.seriesId === book.seriesId).sort(
    (a, b) => (a.seriesIndex ?? 0) - (b.seriesIndex ?? 0),
  )
}

/** Sessions mock pour le livre en cours et un livre déjà lu. */
export const SESSIONS: ReadingSession[] = [
  {
    id: 1,
    bookId: CURRENTLY_READING.book.id,
    startedAt: "2026-08-14T21:10:00",
    durationSec: 32 * 60 + 15,
    startPage: 128,
    endPage: 151,
    pagesRead: 23,
    source: "timer",
  },
  {
    id: 2,
    bookId: CURRENTLY_READING.book.id,
    startedAt: "2026-08-13T07:40:00",
    durationSec: 18 * 60 + 5,
    startPage: 112,
    endPage: 128,
    pagesRead: 16,
    source: "koreader",
  },
  {
    id: 3,
    bookId: CURRENTLY_READING.book.id,
    startedAt: "2026-08-11T22:05:00",
    durationSec: 46 * 60 + 40,
    startPage: 84,
    endPage: 112,
    pagesRead: 28,
    source: "koreader",
  },
  {
    id: 4,
    bookId: CURRENTLY_READING.book.id,
    startedAt: "2026-08-09T20:30:00",
    durationSec: 25 * 60,
    startPage: 60,
    endPage: 84,
    pagesRead: 24,
    source: "manual",
  },
]

/** Highlights mock, deux sources (manuel + KOReader) pour montrer les deux badges. */
export const HIGHLIGHTS: Highlight[] = [
  {
    id: 1,
    bookId: CURRENTLY_READING.book.id,
    text: "On ne revient jamais tout à fait du même endroit qu'on a quitté.",
    note: "à relire pour l'intro du carnet de voyage",
    page: 94,
    chapter: "Chapitre 6",
    highlightedAt: "2026-08-11T22:40:00",
    source: "manual",
  },
  {
    id: 2,
    bookId: CURRENTLY_READING.book.id,
    text: "Le silence, ici, n'est pas une absence : c'est ce qui reste quand on a fini d'avoir peur.",
    note: null,
    page: 121,
    chapter: "Chapitre 7",
    highlightedAt: "2026-08-13T08:02:00",
    source: "koreader",
  },
  {
    id: 3,
    bookId: CURRENTLY_READING.book.id,
    text: "Elle comptait les jours comme d'autres comptent l'argent qui leur reste.",
    note: null,
    page: 140,
    chapter: "Chapitre 8",
    highlightedAt: "2026-08-14T21:35:00",
    source: "koreader",
  },
]

export function sessionsForBook(bookId: number): ReadingSession[] {
  return SESSIONS.filter((s) => s.bookId === bookId)
}

export function highlightsForBook(bookId: number): Highlight[] {
  return HIGHLIGHTS.filter((h) => h.bookId === bookId)
}

/**
 * Pile à lire = "la sélection", une liste curatée à la main — distincte
 * du simple filtre `status === "tbr"` de la Bibliothèque (sous-ensemble
 * non ordonné). `tbrRank` porte l'ordre choisi (1 = prochain lu),
 * volontairement pas dans l'ordre des `id` pour prouver que c'est bien un
 * choix, pas un tri implicite. `tbrNote` (optionnel) est le "pourquoi je
 * veux le lire", affiché seulement s'il existe.
 */
const TBR_ORDER: { id: number; note?: string }[] = [
  { id: 9, note: "Recommandé par C. après notre dernier échange" },
  { id: 17 },
  {
    id: 2,
    note: "Pour enchaîner avant que l'adaptation ne sorte",
  },
  { id: 14 },
  { id: 5 },
]

for (const [i, entry] of TBR_ORDER.entries()) {
  const book = BOOKS.find((b) => b.id === entry.id)
  if (!book) continue
  book.tbrRank = i + 1
  book.tbrNote = entry.note ?? null
}

/** Pile à lire — même pool que la bibliothèque, filtré puis trié par `tbrRank`. */
export const TBR_BOOKS: Book[] = BOOKS.filter((b) => b.status === "tbr").sort(
  (a, b) => (a.tbrRank ?? 0) - (b.tbrRank ?? 0),
)

/** Wishlist — un seul item dans le mock actuel ; voir aussi WISHLIST_EMPTY. */
export const WISHLIST_BOOKS: Book[] = BOOKS.filter((b) => b.status === "wishlist")
