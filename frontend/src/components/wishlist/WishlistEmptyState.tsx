import { BookHeart } from "lucide-react"
import { Button } from "@/components/ui/button"

/**
 * État vide de la wishlist. Un des écrans "sans couverture" cités par
 * AGENTS.md : pas d'ornement de couleur, la hiérarchie vient de l'icône
 * en trait fin (encre, pas d'accent), du poids du titre, et du seul
 * bouton d'encre de l'écran. Ce n'est pas un état d'erreur — la question
 * d'une couleur de signal (réservée aux vrais états d'alerte) ne se pose
 * donc pas ici ; voir SettingsPage pour un cas où elle se pose réellement.
 */
export function WishlistEmptyState() {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <BookHeart className="h-9 w-9 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
      <div>
        <h2 className="text-[17px] font-semibold text-ink">Ta wishlist est vide</h2>
        <p className="mx-auto mt-1.5 max-w-[38ch] text-[13.5px] text-ink-mute">
          Les livres que tu veux lire un jour, sans les posséder encore, vivent ici.
        </p>
      </div>
      <Button size="lg" className="h-11 rounded-[3px] px-5 text-[15px]">
        Ajouter un livre
      </Button>
    </div>
  )
}
