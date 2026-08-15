import type { ReactNode } from "react"
import { NAV_ITEMS } from "@/lib/constants"
import type { NavItem } from "@/types/book"
import { useBooks } from "@/context/books"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { TopNav } from "./TopNav"
import { BottomNav } from "./BottomNav"
import { RailNav } from "./RailNav"

interface AppShellProps {
  activeKey: NavItem["key"]
  children: ReactNode
}

/**
 * Composition unique des trois formes de layout (AGENTS.md « Layouts »),
 * entièrement pilotée par @container sur `.shell` (voir index.css) :
 * aucune détection de largeur en JS, aucune media query. Les trois navs
 * et la carte latérale coexistent dans le DOM ; c'est le CSS qui décide
 * laquelle s'affiche.
 *
 * La carte « En cours » (sidebar) vit ici, en dehors des routes : elle
 * consomme le contexte livres, pas les props d'une page.
 */
export function AppShell({ activeKey, children }: AppShellProps) {
  const { currentlyReading } = useBooks()

  return (
    <div className="shell-frame">
      <div className="shell bg-paper">
        <TopNav items={NAV_ITEMS} activeKey={activeKey} />
        <RailNav items={NAV_ITEMS} activeKey={activeKey} />

        <aside className="shell__sidebar border-r border-line px-5 py-6">
          <CurrentlyReadingCard data={currentlyReading} variant="card" />
        </aside>

        <main className="shell__main px-4 py-4 @min-[700px]:px-6 @min-[700px]:py-6 @min-[1200px]:px-8">
          {children}
        </main>

        <BottomNav items={NAV_ITEMS} activeKey={activeKey} />
      </div>
    </div>
  )
}
