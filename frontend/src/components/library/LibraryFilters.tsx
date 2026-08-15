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
import type { Author, Book, Label } from "@/types/book"
import { STATUS_LABELS } from "@/lib/mock-data"

interface LibraryFiltersProps {
  authors: Author[]
  genres: Label[]
  tags: Label[]
  activeStatus: Book["status"] | "all"
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
 * Filtres statut/auteur/genre/tag — mock visuel uniquement (pas de
 * state, pas d'appel réseau : frontend-dev branchera la logique).
 * Statut en onglets soulignés (filet actif), pas de pastille colorée.
 */
export function LibraryFilters({
  authors,
  genres,
  tags,
  activeStatus,
}: LibraryFiltersProps) {
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex gap-5 overflow-x-auto whitespace-nowrap pb-px">
        {STATUS_ORDER.map((status) => {
          const isActive = status === activeStatus
          const label = status === "all" ? "Tous" : STATUS_LABELS[status]
          return (
            <li key={status}>
              <button
                type="button"
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
          />
        </div>

        <Select defaultValue="all">
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

        <Select defaultValue="all">
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

        <Select defaultValue="all">
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
      </div>
    </div>
  )
}
