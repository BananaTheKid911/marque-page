import { ChevronLeft } from "lucide-react"
import { BOOKS, highlightsForBook, sessionsForBook } from "@/lib/mock-data"
import { BookHero } from "@/components/book/BookHero"
import { BookProgressStat } from "@/components/book/BookProgressStat"
import { SessionHistory } from "@/components/book/SessionHistory"
import { HighlightFeed } from "@/components/book/HighlightFeed"

interface BookDetailPageProps {
  bookId: number
}

/**
 * Page Détail d'un livre. Données statiques (BOOKS + sessions/highlights
 * mock) — frontend-dev remplace par GET /books/{id}, /books/{id}/sessions
 * et /books/{id}/highlights sans toucher au balisage.
 */
export function BookDetailPage({ bookId }: BookDetailPageProps) {
  const book = BOOKS.find((b) => b.id === bookId)

  if (!book) {
    return (
      <div className="flex flex-col items-start gap-4">
        <a
          href="/"
          className="inline-flex items-center gap-1 text-[13.5px] text-ink-mute hover:text-ink"
        >
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          Bibliothèque
        </a>
        <p className="text-[15px] text-ink-mute">Ce livre n'existe pas dans le catalogue.</p>
      </div>
    )
  }

  const sessions = sessionsForBook(book.id)
  const highlights = highlightsForBook(book.id)

  return (
    <div className="flex flex-col gap-8 pb-8">
      <a
        href="/"
        className="inline-flex w-fit items-center gap-1 text-[13.5px] text-ink-mute transition-colors hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Bibliothèque
      </a>

      <BookHero book={book} />

      <div className="flex flex-col gap-8 @min-[700px]:grid @min-[700px]:grid-cols-[minmax(0,1fr)_260px] @min-[700px]:items-start @min-[700px]:gap-8">
        <div className="flex flex-col gap-8">
          <SessionHistory sessions={sessions} />
          <HighlightFeed highlights={highlights} />
        </div>
        <div className="@min-[700px]:sticky @min-[700px]:top-0">
          <BookProgressStat book={book} />
        </div>
      </div>
    </div>
  )
}
