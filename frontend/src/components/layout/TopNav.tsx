import { cn } from "@/lib/utils"
import type { NavItem } from "@/types/book"
import { NAV_ICONS } from "./nav-icons"

interface TopNavProps {
  items: NavItem[]
  activeKey: NavItem["key"]
}

/**
 * Nav en haut, >= 700px de conteneur. Pas de filet soudant la barre au
 * contenu (AGENTS.md « rien ne colle à rien ») : la séparation vient de
 * l'espacement, pas d'une bordure.
 */
export function TopNav({ items, activeKey }: TopNavProps) {
  return (
    <header
      className="shell__topnav items-center justify-between gap-6 px-6 py-4 @min-[1200px]:px-8"
      aria-label="Navigation principale"
    >
      <span className="shrink-0 font-serif text-xl italic text-ink">
        Marque-page
      </span>

      <nav className="flex flex-1 items-center justify-end gap-1">
        <ul className="flex items-center gap-1">
          {items.map((item) => {
            const Icon = NAV_ICONS[item.key]
            const isActive = item.key === activeKey
            const isAdd = item.key === "add"

            if (isAdd) {
              return (
                <li key={item.key} className="ml-2">
                  <a
                    href={item.href}
                    className="flex items-center gap-1.5 rounded-[3px] bg-ink px-4 py-2 text-[15px] text-paper transition-transform active:translate-y-px"
                  >
                    <Icon className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
                    {item.label}
                  </a>
                </li>
              )
            }

            return (
              <li key={item.key}>
                <a
                  href={item.href}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 border-b-2 border-transparent px-3 py-2 text-[15px] transition-colors",
                    isActive
                      ? "border-b-ink text-ink"
                      : "text-ink-mute hover:text-ink",
                  )}
                >
                  <Icon className="h-4 w-4" strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                  {item.label}
                </a>
              </li>
            )
          })}
        </ul>
      </nav>
    </header>
  )
}
