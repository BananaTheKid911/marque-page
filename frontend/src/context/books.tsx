import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import type { ReactNode } from "react"
import { listBooks, listSessions } from "@/lib/api"
import type { CurrentlyReading } from "@/types/book"

interface BooksContextValue {
  /**
   * Livre `reading` désigné comme lecture principale, ou `null` si aucun.
   * Le backend n'a pas d'endpoint `primary=1` : on filtre côté front la
   * liste `status=reading` (peu de livres en cours, la liste est légère).
   */
  currentlyReading: CurrentlyReading | null
  /**
   * Incrémentée après chaque mutation serveur (statut, primary, reorder,
   * timer…) : les pages l'utilisent comme dépendance de refetch pour
   * recharger leurs listes sans round-trip explicite.
   */
  booksVersion: number
  /** À appeler après toute mutation — recharge la carte « En cours » et les pages. */
  notifyBooksChanged: () => void
}

const BooksContext = createContext<BooksContextValue | null>(null)

export function BooksProvider({ children }: { children: ReactNode }) {
  const [currentlyReading, setCurrentlyReading] = useState<CurrentlyReading | null>(null)
  const [booksVersion, setBooksVersion] = useState(0)

  useEffect(() => {
    let cancelled = false

    async function load() {
      try {
        const list = await listBooks({ status: "reading", page_size: 100 })
        if (cancelled) return
        const primary = list.items.find((b) => b.isPrimaryReading) ?? null
        if (!primary) {
          setCurrentlyReading(null)
          return
        }
        const sessions = await listSessions(primary.id)
        if (cancelled) return
        setCurrentlyReading({
          book: primary,
          sessionCount: sessions.total,
          // sessions triées de la plus récente à la plus ancienne.
          lastSessionDurationSec: sessions.items[0]?.durationSec ?? 0,
        })
      } catch {
        // Backend injoignable ou réponse hors contrat : la carte dessine
        // son état vide plutôt que de planter l'app.
        if (!cancelled) setCurrentlyReading(null)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [booksVersion])

  const notifyBooksChanged = useCallback(() => setBooksVersion((v) => v + 1), [])

  const value = useMemo(
    () => ({ currentlyReading, booksVersion, notifyBooksChanged }),
    [currentlyReading, booksVersion, notifyBooksChanged],
  )

  return <BooksContext.Provider value={value}>{children}</BooksContext.Provider>
}

export function useBooks(): BooksContextValue {
  const ctx = useContext(BooksContext)
  if (!ctx) throw new Error("useBooks doit être utilisé dans <BooksProvider>")
  return ctx
}
