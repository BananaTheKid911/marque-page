import type { ReactNode } from "react"
import { cn } from "@/lib/utils"

interface SettingsRowProps {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}

/**
 * Ligne réglage : label + description à gauche, contrôle (input/select/
 * bouton) à droite. Empile en dessous de 480px de conteneur pour rester
 * lisible sur téléphone étroit. Séparateur `--line-2`, jamais de fond
 * différent pour "activer" une ligne — pas de couleur disponible.
 */
export function SettingsRow({ label, hint, children, className }: SettingsRowProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-2 border-b border-line-2 px-4 py-4 last:border-b-0 @min-[420px]:flex-row @min-[420px]:items-center @min-[420px]:justify-between @min-[420px]:gap-4",
        className,
      )}
    >
      <div className="min-w-0">
        <p className="text-[14.5px] text-ink">{label}</p>
        {hint && <p className="mt-0.5 text-[12.5px] text-ink-mute">{hint}</p>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  )
}
