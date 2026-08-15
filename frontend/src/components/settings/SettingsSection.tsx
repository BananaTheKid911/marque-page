import type { ReactNode } from "react"

interface SettingsSectionProps {
  title: string
  description?: string
  children: ReactNode
}

/**
 * Regroupement visuel des Réglages. Écran "sans couverture" (AGENTS.md) :
 * pas d'image, pas d'accent — la hiérarchie tient au label de section en
 * petites capitales et à l'espacement généreux entre blocs, jamais à un
 * fond coloré.
 */
export function SettingsSection({ title, description, children }: SettingsSectionProps) {
  return (
    <section className="flex flex-col gap-3">
      <div>
        <h2 className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-[13px] text-ink-mute">{description}</p>
        )}
      </div>
      <div className="rounded-[4px] border border-line bg-card">{children}</div>
    </section>
  )
}
