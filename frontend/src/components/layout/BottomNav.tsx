import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import type { NavItem } from "@/types/book"
import { NAV_ICONS } from "./nav-icons"

interface BottomNavProps {
  items: NavItem[]
  activeKey: NavItem["key"]
}

/**
 * Barre basse mobile (< 700px de conteneur), 5 entrées, "Ajouter" en
 * pastille d'encre centrale. Cibles tactiles >= 44px (AGENTS.md).
 */
export function BottomNav({ items, activeKey }: BottomNavProps) {
  return (
    <nav
      className="shell__bottomnav border-t border-line bg-card px-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] pt-1"
      aria-label="Navigation principale"
    >
      <ul className="flex w-full items-stretch justify-between">
        {items.map((item) => {
          const Icon = NAV_ICONS[item.key]
          const isActive = item.key === activeKey
          const isAdd = item.key === "add"

          if (isAdd) {
            return (
              <li key={item.key} className="flex flex-1 items-center justify-center">
                <Link
                  to={item.href}
                  aria-label={item.label}
                  className="-mt-3 flex h-11 w-11 items-center justify-center rounded-[3px] bg-ink text-paper shadow-cover transition-transform active:translate-y-px"
                >
                  <Icon className="h-5 w-5" strokeWidth={2} aria-hidden="true" />
                </Link>
              </li>
            )
          }

          return (
            <li key={item.key} className="flex flex-1 justify-center">
              <Link
                to={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex min-h-11 min-w-11 flex-col items-center justify-center gap-0.5 border-t-2 border-transparent px-2 pt-1.5 text-[11px] leading-none",
                  isActive ? "border-t-ink text-ink" : "text-ink-mute",
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
