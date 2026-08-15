import { Link } from "react-router-dom"
import { ChevronLeft } from "lucide-react"

interface PlaceholderPageProps {
  title: string
  description: string
}

/**
 * Écran provisoire pour les routes sans design dessiné (Ajouter, Stats,
 * 404). Strictement fonctionnel — balisage de jalon, pas un habillage
 * validé : design-ui doit le remplacer (écrans « sans couverture »
 * cités par AGENTS.md, la question de la couleur de signal y revient).
 */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <div className="flex flex-col items-start gap-4">
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-[13.5px] text-ink-mute hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Bibliothèque
      </Link>
      <h1 className="text-[19px] font-semibold text-ink">{title}</h1>
      <p className="max-w-prose text-[15px] text-ink-mute">{description}</p>
    </div>
  )
}
