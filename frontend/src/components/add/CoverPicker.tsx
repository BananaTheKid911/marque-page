import { ChevronLeft, ImageOff } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { formatAuthors } from "@/lib/format"
import { SOURCE_LABELS, type SearchCandidate } from "./types"

interface CoverPickerProps {
  candidate: SearchCandidate
  selectedCoverId: string | null
  onSelectCover: (coverId: string) => void
  onConfirm: () => void
  onBack: () => void
  submitting?: boolean
}

/**
 * Deuxième temps du flux d'ajout (spec §4.3) : le livre est identifié,
 * reste à choisir laquelle des couvertures candidates — Open Library et
 * Google Books renvoient rarement le même scan — représente le livre dans
 * la bibliothèque. Aucune image n'est chargée ici (mock local, et de toute
 * façon jamais de hotlink même en prod — AGENTS.md : la couverture choisie
 * sera téléchargée localement par le backend). "Sans couverture" est un
 * choix valide, pas un état dégradé : BookCover affiche déjà très bien un
 * livre sans image.
 *
 * Sélection marquée par un contour d'encre (2px), jamais une couleur —
 * seul levier disponible pour "actif" en dehors de la masse noire.
 */
export function CoverPicker({
  candidate,
  selectedCoverId,
  onSelectCover,
  onConfirm,
  onBack,
  submitting,
}: CoverPickerProps) {
  return (
    <div className="flex flex-col gap-6">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex w-fit items-center gap-1 text-[13.5px] text-ink-mute transition-colors hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Retour aux résultats
      </button>

      <div>
        <h2 className="text-balance text-[19px] font-semibold leading-snug text-ink">
          {candidate.title}
        </h2>
        <p className="mt-1 text-[13.5px] text-ink-soft">{formatAuthors(candidate.authors)}</p>
      </div>

      <div>
        <p className="mb-3 text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
          Choisir une couverture
        </p>
        <ul
          className="grid grid-cols-3 gap-x-3 gap-y-5
            @min-[700px]:grid-cols-[repeat(auto-fill,minmax(118px,1fr))] @min-[700px]:gap-x-4
            pointer-coarse:@min-[1200px]:grid-cols-[repeat(auto-fill,minmax(132px,1fr))]"
        >
          {candidate.covers.map((cover) => {
            const isSelected = cover.id === selectedCoverId
            return (
              <li key={cover.id}>
                <button
                  type="button"
                  onClick={() => onSelectCover(cover.id)}
                  aria-pressed={isSelected}
                  className="group block w-full text-left"
                >
                  <div
                    className={cn(
                      "flex aspect-[2/3] items-center justify-center overflow-hidden rounded-[2px] border bg-line-2/50 transition-colors",
                      isSelected ? "border-2 border-ink" : "border border-line-2 hover:border-ink-mute",
                    )}
                  >
                    {cover.hasImage ? (
                      <span className="px-2 text-center text-[11px] leading-snug text-ink-mute">
                        Vignette à charger
                      </span>
                    ) : (
                      <ImageOff className="h-5 w-5 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
                    )}
                  </div>
                  <p className="mt-1.5 truncate text-[11px] uppercase tracking-[0.08em] text-ink-mute">
                    {SOURCE_LABELS[cover.source]}
                  </p>
                  <p className="truncate text-[11.5px] text-ink-soft">
                    {cover.hasImage ? cover.label : "Aucune image"}
                  </p>
                </button>
              </li>
            )
          })}
        </ul>
      </div>

      <Button
        type="button"
        onClick={onConfirm}
        disabled={submitting}
        className="h-11 w-full rounded-[3px] text-[15px] @min-[420px]:w-auto @min-[420px]:self-start @min-[420px]:px-6"
      >
        {submitting ? "Ajout…" : "Ajouter à ma bibliothèque"}
      </Button>
    </div>
  )
}
