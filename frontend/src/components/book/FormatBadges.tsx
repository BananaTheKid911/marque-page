import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { BookFormat } from "@/types/book"

interface FormatBadgesProps {
  formats: BookFormat[]
}

const FORMAT_LABELS: Record<BookFormat["type"], string> = {
  physique: "Physique",
  digital: "Digital",
  audio: "Audio",
}

/**
 * Format (physique/digital/audio) × possession, deux dimensions
 * orthogonales au statut (décision produit du 15/08/2026). La masse noire
 * pleine est réservée à L'UNIQUE action primaire de l'écran (AGENTS.md) —
 * "possédé" ne peut donc pas être un badge rempli d'encre. Le levier ici
 * est le contour (plein/pointillé) + le poids du texte, jamais une
 * couleur : possédé = contour plein `--ink`, texte medium ; non possédé
 * (emprunté, écouté sans achat…) = contour pointillé `--ink-mute`, texte
 * normal.
 */
export function FormatBadges({ formats }: FormatBadgesProps) {
  if (formats.length === 0) return null

  return (
    <ul className="flex flex-wrap gap-1.5" aria-label="Formats et possession">
      {formats.map((format) => (
        <li key={format.type}>
          <Badge
            variant="outline"
            className={cn(
              "rounded-[3px] px-2 py-1 text-[11.5px]",
              format.owned
                ? "border-ink font-medium text-ink"
                : "border-dashed border-ink-mute font-normal text-ink-mute",
            )}
          >
            {FORMAT_LABELS[format.type]}
            <span className="mx-1 opacity-50" aria-hidden="true">
              ·
            </span>
            {format.owned ? "possédé" : "non possédé"}
          </Badge>
        </li>
      ))}
    </ul>
  )
}
