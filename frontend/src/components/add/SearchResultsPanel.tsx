import { BookOpen, ChevronRight, SearchX, WifiOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { formatAuthors } from "@/lib/format"
import { SOURCE_LABELS, type SearchCandidate } from "./types"

export type SearchStatus = "idle" | "loading" | "error" | "empty" | "done"

interface SearchResultsPanelProps {
  status: SearchStatus
  results: SearchCandidate[]
  onSelect: (candidate: SearchCandidate) => void
  onRetry: () => void
}

/**
 * États du résultat de recherche (spec §4) : chargement, aucun résultat,
 * erreur réseau, liste de candidats. `status === "idle"` (aucune recherche
 * lancée) ne rend rien — c'est à l'appelant de ne pas monter ce composant
 * avant la première soumission.
 *
 * L'état d'erreur n'utilise que la famille encre (--ink-soft, --ink-mute) :
 * AGENTS.md réserve une éventuelle couleur de signal à une décision de
 * Jordy sur un cas réel, pas à trancher ici. Voir le rapport de session.
 */
export function SearchResultsPanel({ status, results, onSelect, onRetry }: SearchResultsPanelProps) {
  if (status === "idle") return null

  if (status === "loading") {
    return (
      <ul aria-label="Recherche en cours" className="flex flex-col gap-3" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <li
            key={i}
            className="flex items-center gap-3 rounded-[4px] border border-line bg-card p-3"
          >
            <div className="aspect-[2/3] w-11 shrink-0 animate-pulse rounded-[2px] bg-line-2" />
            <div className="flex flex-1 flex-col gap-2">
              <div className="h-3 w-3/5 animate-pulse rounded-full bg-line-2" />
              <div className="h-2.5 w-2/5 animate-pulse rounded-full bg-line-2" />
            </div>
          </li>
        ))}
      </ul>
    )
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-start gap-3 rounded-[4px] border border-line bg-card p-4">
        <div className="flex items-center gap-2 text-ink-soft">
          <WifiOff className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
          <p className="text-[13.5px]">Recherche impossible : connexion au serveur indisponible.</p>
        </div>
        <Button
          type="button"
          variant="outline"
          onClick={onRetry}
          className="h-9 rounded-[3px] px-4 text-[13.5px]"
        >
          Réessayer
        </Button>
      </div>
    )
  }

  if (status === "empty") {
    return (
      <div className="flex flex-col items-center gap-3 py-12 text-center">
        <SearchX className="h-8 w-8 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
        <div>
          <p className="text-[14.5px] text-ink">Aucun résultat pour cette recherche.</p>
          <p className="mx-auto mt-1 max-w-[36ch] text-[12.5px] text-ink-mute">
            Vérifie l'orthographe, ou essaie l'ISBN imprimé au dos du livre.
          </p>
        </div>
      </div>
    )
  }

  return (
    <ul aria-label="Résultats de recherche" className="flex flex-col gap-2">
      {results.map((candidate) => (
        <li key={candidate.id}>
          <button
            type="button"
            onClick={() => onSelect(candidate)}
            className="flex min-h-[44px] w-full items-center gap-3 rounded-[4px] border border-line bg-card p-3 text-left transition-colors hover:bg-line-2/40 focus-visible:bg-line-2/40"
          >
            <div className="flex aspect-[2/3] w-11 shrink-0 items-center justify-center overflow-hidden rounded-[2px] border border-line-2 bg-line-2/60">
              <BookOpen className="h-4 w-4 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-[14px] font-medium text-ink">{candidate.title}</p>
              <p className="truncate text-[12.5px] text-ink-mute">
                {formatAuthors(candidate.authors)}
              </p>
              <div className="mt-1 flex flex-wrap items-center gap-1.5">
                <Badge
                  variant="outline"
                  className="rounded-[3px] border-line-2 px-1.5 text-[10px] font-medium uppercase tracking-[0.1em] text-ink-mute"
                >
                  {SOURCE_LABELS[candidate.source]}
                </Badge>
                {candidate.publishedDate && (
                  <span className="text-[11px] tabular-nums text-ink-mute">
                    {candidate.publishedDate}
                  </span>
                )}
                {candidate.publisher && (
                  <span className="truncate text-[11px] text-ink-mute">{candidate.publisher}</span>
                )}
              </div>
            </div>

            <ChevronRight className="h-4 w-4 shrink-0 text-ink-mute" aria-hidden="true" />
          </button>
        </li>
      ))}
    </ul>
  )
}
