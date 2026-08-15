import { useId, useState } from "react"
import { Check, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface SessionEndControlProps {
  /** page courante du livre — valeur par défaut du champ, comme l'ancien prompt */
  currentPage: number
  /** `null` si le nombre de pages total n'est pas connu — pas de borne affichée */
  totalPages: number | null
  busy?: boolean
  /** confirmation — reçoit la page saisie */
  onConfirm: (endPage: number) => void
  /** annulation — ne doit rien envoyer au serveur (contrairement à l'ancien prompt) */
  onCancel: () => void
}

/**
 * Remplace le `window.prompt` natif de fin de session. Panneau inline qui
 * prend la place du bouton "Arrêter le chrono" — même emplacement, la masse
 * noire (AGENTS.md, un seul bouton d'encre par écran) passe du déclencheur
 * au bouton de confirmation pendant que le panneau est ouvert.
 *
 * Annuler ne déclenche aucun appel réseau : contrairement au prompt natif
 * (qui envoyait `book.currentPage` inchangé sur Échap), fermer sans valider
 * ne doit rien modifier côté serveur — un "annuler" qui écrit quand même
 * serait trompeur.
 */
export function SessionEndControl({
  currentPage,
  totalPages,
  busy = false,
  onConfirm,
  onCancel,
}: SessionEndControlProps) {
  const [value, setValue] = useState(String(currentPage))
  const inputId = useId()

  const parsed = Number.parseInt(value, 10)
  const endPage = Number.isFinite(parsed) ? Math.max(0, parsed) : 0
  const overTotal = totalPages != null && endPage > totalPages

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (busy) return
    onConfirm(endPage)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-wrap items-end gap-3 rounded-[4px] border border-line bg-card px-4 py-3 shadow-card"
    >
      <div className="flex flex-col gap-1">
        <label
          htmlFor={inputId}
          className="text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute"
        >
          Page atteinte
        </label>
        <Input
          id={inputId}
          type="number"
          inputMode="numeric"
          min={0}
          max={totalPages ?? undefined}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          autoFocus
          className="h-11 w-28 rounded-[3px] border-line text-[15px] tabular-nums text-ink focus-visible:ring-ink/30"
        />
        {overTotal && (
          <p className="text-[12px] text-ink-mute">dépasse les {totalPages} pages du livre</p>
        )}
      </div>

      <div className="flex gap-2">
        <Button
          type="submit"
          size="lg"
          className="h-11 rounded-[3px] px-5 text-[15px]"
          disabled={busy}
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          Confirmer
        </Button>
        <Button
          type="button"
          variant="outline"
          size="lg"
          className="h-11 rounded-[3px] px-4 text-[15px]"
          onClick={onCancel}
          disabled={busy}
        >
          <X className="h-4 w-4" aria-hidden="true" />
          Annuler
        </Button>
      </div>
    </form>
  )
}
