import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { STATUS_LABELS } from "@/lib/constants"
import type { BookStatus } from "@/types/book"

/**
 * Statuts atteignables depuis ce contrôle générique. "read" en est
 * volontairement exclu : ce passage exige une `finished_at` (SPEC.md §5)
 * que le bouton dédié "Marquer comme lu" de BookHero fournit déjà — le
 * dupliquer ici sans date de fin créerait un deuxième chemin incohérent
 * vers le même état.
 */
const SELECTABLE_STATUSES: BookStatus[] = ["wishlist", "tbr", "reading", "on_hold", "dnf"]

interface StatusControlProps {
  status: BookStatus
  busy?: boolean
  onChange: (status: BookStatus) => void
}

/**
 * Changement de statut manuel, valable pour n'importe quel livre quel que
 * soit son état actuel — en particulier wishlist → tbr ("je l'ai acheté").
 * AGENTS.md : un seul bouton plein d'encre par écran (déjà pris par l'action
 * primaire de BookHero) ; ce contrôle est donc un menu, jamais un deuxième
 * bouton rempli. Le déclencheur shadcn (`border-input`, fond transparent)
 * a le même poids visuel qu'un bouton outline — cohérent avec les autres
 * actions secondaires de la fiche.
 */
export function StatusControl({ status, busy = false, onChange }: StatusControlProps) {
  return (
    <div>
      <label
        htmlFor="book-status-control"
        className="mb-1.5 block text-[10px] font-medium uppercase tracking-[0.16em] text-ink-mute"
      >
        Changer le statut
      </label>
      <Select
        value={status}
        disabled={busy}
        onValueChange={(value) => {
          if (value !== status) onChange(value as BookStatus)
        }}
      >
        <SelectTrigger
          id="book-status-control"
          className="h-9 w-48 rounded-[3px] border-line bg-card text-[13.5px] text-ink"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {SELECTABLE_STATUSES.map((value) => (
            <SelectItem key={value} value={value} className="text-[13.5px]">
              {STATUS_LABELS[value]}
            </SelectItem>
          ))}
          {/* Le statut courant reste sélectionnable même s'il n'est pas
              dans SELECTABLE_STATUSES (cas "read", atteint uniquement par
              le bouton dédié) — sinon <Select> n'a pas de libellé à
              afficher pour la valeur actuelle. */}
          {!SELECTABLE_STATUSES.includes(status) && (
            <SelectItem value={status} className="text-[13.5px]">
              {STATUS_LABELS[status]}
            </SelectItem>
          )}
        </SelectContent>
      </Select>
    </div>
  )
}
