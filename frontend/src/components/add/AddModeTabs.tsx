import { ScanLine, Search } from "lucide-react"
import { cn } from "@/lib/utils"

export type AddMode = "isbn" | "text"

interface AddModeTabsProps {
  mode: AddMode
  onChange: (mode: AddMode) => void
}

const TABS: { key: AddMode; label: string; icon: typeof ScanLine }[] = [
  { key: "isbn", label: "Scanner / ISBN", icon: ScanLine },
  { key: "text", label: "Titre, auteur", icon: Search },
]

/**
 * Bascule entre les deux méthodes de recherche. Même mécanique que les
 * onglets de statut de LibraryFilters : filet sous l'élément actif,
 * jamais de pastille colorée (AGENTS.md, levier de hiérarchie n°3).
 * Cibles ≥ 44px, plein-largeur à deux colonnes égales pour rester
 * confortable au pouce en mobile comme au rail tactile.
 */
export function AddModeTabs({ mode, onChange }: AddModeTabsProps) {
  return (
    <div role="tablist" aria-label="Méthode de recherche" className="flex border-b border-line-2">
      {TABS.map(({ key, label, icon: Icon }) => {
        const isActive = key === mode
        return (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(key)}
            className={cn(
              "flex min-h-11 flex-1 items-center justify-center gap-2 border-b-2 py-2.5 text-[15px] transition-colors",
              isActive
                ? "border-b-ink font-medium text-ink"
                : "border-b-transparent text-ink-mute hover:text-ink",
            )}
          >
            <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            {label}
          </button>
        )
      })}
    </div>
  )
}
