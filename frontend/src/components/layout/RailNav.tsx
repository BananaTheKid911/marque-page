import { Link } from "react-router-dom"
import { cn } from "@/lib/utils"
import type { NavItem } from "@/types/book"
import { NAV_ICONS } from "./nav-icons"

interface RailNavProps {
  items: NavItem[]
  activeKey: NavItem["key"]
}

/**
 * Rail vertical, réservé au tactile (>= 1200px de conteneur ET
 * pointer: coarse — cf. AGENTS.md). Fixe, ne défile jamais : c'est
 * .shell__main qui porte tout le scroll.
 */
export function RailNav({ items, activeKey }: RailNavProps) {
  return (
    <nav
      className="shell__rail w-[176px] flex-col gap-1 border-r border-line px-3 py-6"
      aria-label="Navigation principale"
    >
      <span className="mb-6 px-2 font-serif text-xl italic text-ink">
        Marque-page
      </span>

      <ul className="flex flex-col gap-1">
        {items.map((item) => {
          const Icon = NAV_ICONS[item.key]
          const isActive = item.key === activeKey
          const isAdd = item.key === "add"

          if (isAdd) {
            return (
              <li key={item.key} className="my-2">
                <Link
                  to={item.href}
                  className="flex min-h-11 items-center gap-2.5 rounded-[3px] bg-ink px-3 text-[15px] text-paper transition-transform active:translate-y-px"
                >
                  <Icon className="h-5 w-5 shrink-0" strokeWidth={2} aria-hidden="true" />
                  {item.label}
                </Link>
              </li>
            )
          }

          return (
            <li key={item.key}>
              <Link
                to={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex min-h-11 items-center gap-2.5 border-l-2 border-transparent pl-3 pr-2 text-[15px]",
                  isActive ? "border-l-ink text-ink" : "text-ink-mute",
                )}
              >
                <Icon className="h-5 w-5 shrink-0" strokeWidth={isActive ? 2.25 : 1.75} aria-hidden="true" />
                {item.label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
