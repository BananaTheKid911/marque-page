import { Outlet, Route, Routes, useLocation } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { LibraryPage } from "@/pages/LibraryPage"
import { BookDetailPage } from "@/pages/BookDetailPage"
import { ToReadPage } from "@/pages/ToReadPage"
import { WishlistPage } from "@/pages/WishlistPage"
import { SettingsPage } from "@/pages/SettingsPage"
import { PlaceholderPage } from "@/pages/PlaceholderPage"
import type { NavItem } from "@/types/book"

/**
 * Routage réel (react-router) — remplace le routage QA de résolution
 * manuelle qui vivait ici. Les liens du shell (TopNav/BottomNav/RailNav)
 * et les couvertures sont des <Link> react-router : navigation SPA sans
 * rechargement, l'historique navigateur reste natif.
 */

function activeKeyForPath(pathname: string): NavItem["key"] {
  if (pathname === "/pile-a-lire") return "tbr"
  if (pathname === "/ajouter") return "add"
  if (pathname === "/stats") return "stats"
  if (pathname === "/reglages" || pathname.startsWith("/reglages/")) return "settings"
  if (pathname === "/livres" || pathname.startsWith("/livres/")) return "library"
  if (pathname === "/wishlist") return "library"
  return "library"
}

/** Coquille : AppShell calcule sa nav active depuis la route courante.
 * Le wrapper flex `h-dvh` fournit la hauteur que `.shell-frame` attend
 * (index.css) — la chaîne html/body/#root en 100% ne suffit pas en mobile
 * (barre d'adresse dynamique). */
function ShellLayout() {
  const location = useLocation()
  const activeKey = activeKeyForPath(location.pathname)
  return (
    <div className="flex h-dvh flex-col">
      <div className="min-h-0 flex-1">
        <AppShell activeKey={activeKey}>
          <Outlet />
        </AppShell>
      </div>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route element={<ShellLayout />}>
        <Route index element={<LibraryPage />} />
        <Route path="pile-a-lire" element={<ToReadPage />} />
        <Route path="livres/:bookId" element={<BookDetailPage />} />
        <Route path="wishlist" element={<WishlistPage />} />
        <Route path="reglages" element={<SettingsPage />} />
        <Route
          path="ajouter"
          element={
            <PlaceholderPage
              title="Ajouter un livre"
              description="Écran de création (recherche ISBN / saisie manuelle) pas encore dessiné."
            />
          }
        />
        <Route
          path="stats"
          element={
            <PlaceholderPage
              title="Statistiques"
              description="Écran de statistiques pas encore dessiné."
            />
          }
        />
        <Route
          path="*"
          element={
            <PlaceholderPage title="Page introuvable" description="Cette adresse ne mène nulle part." />
          }
        />
      </Route>
    </Routes>
  )
}

export default App
