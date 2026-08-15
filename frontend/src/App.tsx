import { useEffect, useState } from "react"
import { AppShell } from "@/components/layout/AppShell"
import { LibraryPage } from "@/pages/LibraryPage"
import { BookDetailPage } from "@/pages/BookDetailPage"
import { ToReadPage } from "@/pages/ToReadPage"
import { WishlistPage } from "@/pages/WishlistPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { CURRENTLY_READING } from "@/lib/mock-data"
import type { NavItem } from "@/types/book"

/**
 * Routage minimal, pour la QA visuelle uniquement — PAS un vrai routeur.
 * frontend-dev le remplacera par react-router (ou équivalent) quand la
 * logique d'état/navigation réelle sera branchée ; ce fichier ne fait que
 * lire `location.pathname`/`search` au montage et sur "popstate", pour que
 * chaque page dessinée par design-ui soit atteignable dans le navigateur.
 * Les liens <a href> existants (BottomNav, TopNav, RailNav, BookCover, …)
 * fonctionnent tels quels : ce sont de vrais chemins, pas des ancres JS.
 */
function resolveRoute(pathname: string, search: string) {
  if (pathname === "/" || pathname === "") {
    const serie = new URLSearchParams(search).get("serie")
    return {
      activeKey: "library" as NavItem["key"],
      node: <LibraryPage seriesFilterId={serie ? Number(serie) : undefined} />,
    }
  }
  if (pathname.startsWith("/livres/")) {
    const id = Number(pathname.split("/")[2])
    return { activeKey: "library" as NavItem["key"], node: <BookDetailPage bookId={id} /> }
  }
  if (pathname === "/pile-a-lire") {
    return { activeKey: "tbr" as NavItem["key"], node: <ToReadPage /> }
  }
  if (pathname === "/wishlist") {
    const empty = new URLSearchParams(search).get("empty") === "1"
    return {
      activeKey: "library" as NavItem["key"],
      node: <WishlistPage books={empty ? [] : undefined} />,
    }
  }
  if (pathname === "/reglages") {
    return { activeKey: "settings" as NavItem["key"], node: <SettingsPage /> }
  }
  return { activeKey: "library" as NavItem["key"], node: <LibraryPage /> }
}

/** Barre de QA visuelle, retirée quand le vrai routeur arrive côté frontend-dev. */
function DevRouteBar() {
  const links: { href: string; label: string }[] = [
    { href: "/", label: "Bibliothèque" },
    { href: "/?serie=1", label: "Bibliothèque (série)" },
    { href: `/livres/${CURRENTLY_READING.book.id}`, label: "Détail (en cours, principal)" },
    { href: "/livres/6", label: "Détail (en cours, secondaire)" },
    { href: "/livres/2", label: "Détail (sans sessions)" },
    { href: "/livres/3", label: "Détail (série, formats, prix)" },
    { href: "/livres/8", label: "Détail (en pause)" },
    { href: "/pile-a-lire", label: "Pile à lire" },
    { href: "/wishlist", label: "Wishlist" },
    { href: "/wishlist?empty=1", label: "Wishlist (vide)" },
    { href: "/reglages", label: "Réglages" },
  ]

  return (
    <div className="flex shrink-0 flex-wrap gap-x-3 gap-y-1 border-b border-line bg-card px-3 py-1.5 text-[11px]">
      <span className="font-medium uppercase tracking-[0.1em] text-ink-mute">QA</span>
      {links.map((link) => (
        <a key={link.href} href={link.href} className="text-ink-mute underline hover:text-ink">
          {link.label}
        </a>
      ))}
    </div>
  )
}

function App() {
  const [location, setLocation] = useState(() => ({
    pathname: window.location.pathname,
    search: window.location.search,
  }))

  useEffect(() => {
    const onPopState = () =>
      setLocation({ pathname: window.location.pathname, search: window.location.search })
    window.addEventListener("popstate", onPopState)
    return () => window.removeEventListener("popstate", onPopState)
  }, [])

  const { activeKey, node } = resolveRoute(location.pathname, location.search)

  return (
    <div className="flex h-dvh flex-col">
      <DevRouteBar />
      <div className="min-h-0 flex-1">
        <AppShell activeKey={activeKey} currentlyReading={CURRENTLY_READING}>
          {node}
        </AppShell>
      </div>
    </div>
  )
}

export default App
