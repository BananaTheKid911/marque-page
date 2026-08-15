import { Search } from "lucide-react"
import { cn } from "@/lib/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import type { Author, Book, Label, Series } from "@/types/book"
import { STATUS_LABELS } from "@/lib/constants"

export interface LibraryFilterState {
  /** `status` du GET /books ; "all" = pas de filtre. */
  status: Book["status"] | "all"
  /**
   * Série active : changer de série change le COMPORTEMENT de la grille
   * (tri par tome + badge), pas juste son contenu — c'est LibraryPage qui
   * porte cette différence, pas ce composant.
   */
  seriesId: number | "all"
  /** recherche `q` : sous-chaîne titre/sous-titre */
  q: string
  authorId: number | "all"
  genreId: number | "all"
  tagId: number | "all"
}

interface LibraryFiltersProps {
  authors: Author[]
  genres: Label[]
  tags: Label[]
  series: Series[]
  filters: LibraryFilterState
  onChange: (patch: Partial<LibraryFilterState>) => void
}

const STATUS_ORDER: (Book["status"] | "all")[] = [
  "all",
  "tbr",
  "reading",
  "read",
  "on_hold",
  "dnf",
  "wishlist",
]

/**
 * Filtres statut/auteur/genre/tag — composant contrôlé : l'état vit dans
 * LibraryPage (qui construit la query GET /books), ce composant ne fait
 * que remonter les changements. La recherche est débouncée par l'appelant.
 */
export function LibraryFilters({
  authors,
  genres,
  tags,
  series,
  filters,
  onChange,
}: LibraryFiltersProps) {
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex gap-5 overflow-x-auto whitespace-nowrap pb-px">
        {STATUS_ORDER.map((status) => {
          const isActive = status === filters.status
          const label = status === "all" ? "Tous" : STATUS_LABELS[status]
          return (
            <li key={status}>
              <button
                type="button"
                onClick={() => onChange({ status })}
                className={cn(
                  "border-b-2 border-transparent py-2 text-[15px] transition-colors",
                  isActive
                    ? "border-b-ink text-ink"
                    : "text-ink-mute hover:text-ink",
                )}
              >
                {label}
              </button>
            </li>
          )
        })}
      </ul>

      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <div className="relative w-full max-w-[220px] shrink-0">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2 text-ink-mute" />
          <Input
            type="search"
            placeholder="Rechercher un titre…"
            className="pl-8"
            value={filters.q}
            onChange={(e) => onChange({ q: e.target.value })}
          />
        </div>

        <Select
          value={String(filters.authorId)}
          onValueChange={(v) => onChange({ authorId: v === "all" ? "all" : Number(v) })}
        >
          <SelectTrigger className="shrink-0">
            <SelectValue placeholder="Auteur" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les auteurs</SelectItem>
            {authors.map((author) => (
              <SelectItem key={author.id} value={String(author.id)}>
                {author.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={String(filters.genreId)}
          onValueChange={(v) => onChange({ genreId: v === "all" ? "all" : Number(v) })}
        >
          <SelectTrigger className="shrink-0">
            <SelectValue placeholder="Genre" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les genres</SelectItem>
            {genres.map((genre) => (
              <SelectItem key={genre.id} value={String(genre.id)}>
                {genre.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={String(filters.tagId)}
          onValueChange={(v) => onChange({ tagId: v === "all" ? "all" : Number(v) })}
        >
          <SelectTrigger className="shrink-0">
            <SelectValue placeholder="Tag" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les tags</SelectItem>
            {tags.map((tag) => (
              <SelectItem key={tag.id} value={String(tag.id)}>
                {tag.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {series.length > 0 && (
          <Select
            value={String(filters.seriesId)}
            onValueChange={(v) => onChange({ seriesId: v === "all" ? "all" : Number(v) })}
          >
            <SelectTrigger className="shrink-0">
              <SelectValue placeholder="Série" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les séries</SelectItem>
              {series.map((s) => (
                <SelectItem key={s.id} value={String(s.id)}>
                  {s.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>
    </div>
  )
}
