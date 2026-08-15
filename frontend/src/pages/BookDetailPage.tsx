import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ChevronLeft } from "lucide-react"
import {
  ApiError,
  getBook,
  listHighlights,
  listSessions,
  setBookStatus,
  startTimer,
  stopTimer,
  updateBook,
} from "@/lib/api"
import { useBooks } from "@/context/books"
import { useAsyncData } from "@/lib/hooks"
import { BookHero, type BookHeroTimerState } from "@/components/book/BookHero"
import { BookProgressStat } from "@/components/book/BookProgressStat"
import { SessionHistory } from "@/components/book/SessionHistory"
import { HighlightFeed } from "@/components/book/HighlightFeed"

// ---------------------------------------------------------------------------
// Persistance du chrono (AGENTS.md : le timer survit à un rechargement
// d'onglet). La session elle-même vit côté serveur (`POST /timer/start`),
// le localStorage ne garde que la date de début pour afficher la durée
// écoulée sans dépendre d'un serveur qui aurait redémarré.
// ---------------------------------------------------------------------------

const TIMER_STORAGE_KEY = "marquepage:activeTimer"

interface StoredTimer {
  bookId: number
  startedAt: string
}

function readStoredTimer(): StoredTimer | null {
  try {
    const raw = localStorage.getItem(TIMER_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredTimer
    if (typeof parsed.bookId !== "number" || typeof parsed.startedAt !== "string") return null
    return parsed
  } catch {
    return null
  }
}

function writeStoredTimer(bookId: number, startedAt: string): void {
  try {
    localStorage.setItem(TIMER_STORAGE_KEY, JSON.stringify({ bookId, startedAt }))
  } catch {
    /* localStorage indisponible : le chrono serveur reste correct */
  }
}

function clearStoredTimer(): void {
  try {
    localStorage.removeItem(TIMER_STORAGE_KEY)
  } catch {
    /* noop */
  }
}

function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message
  return String(err)
}

interface ActiveTimer {
  startedAt: string
}

/**
 * Page Détail d'un livre — GET /books/{id} + sessions + highlights.
 * Les boutons de BookHero sont câblés : chrono (POST /timer/start|stop),
 * passage manuel tbr/on_hold → reading (POST /books/{id}/status), lecture
 * principale (PATCH is_primary_reading) et fin de lecture (status=read).
 */
export function BookDetailPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const id = Number(bookId)
  const invalidId = !Number.isInteger(id) || id <= 0

  const { booksVersion, notifyBooksChanged } = useBooks()

  const bookData = useAsyncData(() => getBook(id), [id, booksVersion])
  const sessionsData = useAsyncData(() => listSessions(id), [id, booksVersion])
  const highlightsData = useAsyncData(() => listHighlights(id), [id, booksVersion])

  const book = bookData.data
  const sessions = sessionsData.data?.items ?? null

  // --- chrono de session ---
  const [activeTimer, setActiveTimer] = useState<ActiveTimer | null>(null)
  const [now, setNow] = useState(() => Date.now())

  // Détection d'un chrono ouvert au (re)chargement : le serveur fait foi
  // (une session `timer` sans `ended_at`), le localStorage fournit la date
  // de début exacte pour l'affichage après rechargement d'onglet.
  useEffect(() => {
    if (!sessions) return
    const open = sessions.find((s) => s.source === "timer" && !s.endedAt)
    if (open) {
      const stored = readStoredTimer()
      const startedAt = stored?.bookId === id ? stored.startedAt : open.startedAt
      setActiveTimer({ startedAt })
      setNow(Date.now())
    } else {
      setActiveTimer(null)
      if (readStoredTimer()) clearStoredTimer()
    }
  }, [id, sessions])

  // Tick : une seconde, uniquement quand un chrono est actif.
  useEffect(() => {
    if (!activeTimer) return
    const interval = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(interval)
  }, [activeTimer])

  const elapsedSec = activeTimer
    ? Math.max(0, Math.floor((now - new Date(activeTimer.startedAt).getTime()) / 1000))
    : 0
  const timerState: BookHeroTimerState | null = activeTimer ? { running: true, elapsedSec } : null

  const [busy, setBusy] = useState(false)
  const [mutationError, setMutationError] = useState<string | null>(null)

  async function runMutation(action: () => Promise<unknown>) {
    setBusy(true)
    setMutationError(null)
    try {
      await action()
      notifyBooksChanged()
    } catch (err) {
      setMutationError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  function handleStartSession() {
    if (busy || !book) return
    void runMutation(async () => {
      await startTimer(id)
      const startedAt = new Date().toISOString()
      writeStoredTimer(id, startedAt)
      setActiveTimer({ startedAt })
      setNow(Date.now())
    })
  }

  function handleStopSession() {
    if (busy || !book) return
    // TODO design-ui : un vrai contrôle de fin de session (saisie de page)
    // remplacerait ce prompt natif — à dessiner avec l'écran timer.
    const raw = window.prompt("Page atteinte à la fin de cette session ?", String(book.currentPage))
    const endPage = raw == null ? book.currentPage : Math.max(0, Number.parseInt(raw, 10) || 0)
    void runMutation(async () => {
      await stopTimer(id, endPage)
      clearStoredTimer()
      setActiveTimer(null)
    })
  }

  function handleMarkReading() {
    if (busy) return
    void runMutation(() => setBookStatus(id, { status: "reading" }))
  }

  function handleTogglePrimary() {
    if (busy || !book) return
    void runMutation(() => updateBook(id, { is_primary_reading: !book.isPrimaryReading }))
  }

  function handleMarkRead() {
    if (busy) return
    const finishedAt = new Date().toISOString().slice(0, 10)
    void runMutation(() => setBookStatus(id, { status: "read", finished_at: finishedAt }))
  }

  if (invalidId || (bookData.error && bookData.error instanceof ApiError && bookData.error.status === 404)) {
    return (
      <div className="flex flex-col items-start gap-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-[13.5px] text-ink-mute hover:text-ink"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Bibliothèque
        </Link>
        <p className="text-[15px] text-ink-mute">Ce livre n'existe pas dans le catalogue.</p>
      </div>
    )
  }

  if (bookData.error) {
    return (
      <div className="flex flex-col items-start gap-4">
        <Link
          to="/"
          className="inline-flex items-center gap-1 text-[13.5px] text-ink-mute hover:text-ink"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Bibliothèque
        </Link>
        <p className="text-[15px] text-ink-mute">{errorMessage(bookData.error)}</p>
        <button
          type="button"
          onClick={bookData.reload}
          className="rounded-[3px] border border-ink px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-card"
        >
          Réessayer
        </button>
      </div>
    )
  }

  if (!book) return null

  return (
    <div className="flex flex-col gap-8 pb-8">
      <Link
        to="/"
        className="inline-flex w-fit items-center gap-1 text-[13.5px] text-ink-mute transition-colors hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Bibliothèque
      </Link>

      <BookHero
        book={book}
        timer={timerState}
        busy={busy}
        error={mutationError}
        onStartSession={handleStartSession}
        onStopSession={handleStopSession}
        onMarkReading={handleMarkReading}
        onTogglePrimary={handleTogglePrimary}
        onMarkRead={handleMarkRead}
      />

      <div className="flex flex-col gap-8 @min-[700px]:grid @min-[700px]:grid-cols-[minmax(0,1fr)_260px] @min-[700px]:items-start @min-[700px]:gap-8">
        <div className="flex flex-col gap-8">
          <SessionHistory sessions={sessions ?? []} loading={sessionsData.loading} />
          <HighlightFeed highlights={highlightsData.data?.items ?? []} />
        </div>
        <div className="@min-[700px]:sticky @min-[700px]:top-0">
          <BookProgressStat book={book} />
        </div>
      </div>
    </div>
  )
}
