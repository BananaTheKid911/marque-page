import { Check } from "lucide-react"
import { formatAuthors, formatDuration } from "@/lib/format"
import type { KoreaderBookPreview } from "@/types/koreader"

interface KoreaderBookRowProps {
  book: KoreaderBookPreview
}

/**
 * Ligne d'un livre dans l'aperçu (§4.3). Le statut « rattaché / à
 * rattacher » se lit au texte du label et au poids de l'icône, jamais à
 * une couleur : le check plein en encre pour un rattachement acquis, un
 * simple point de suspension typographique pour ce qui reste à trancher
 * — pas d'icône "alerte" ici, ce n'est pas une erreur, juste une étape
 * suivante.
 */
export function KoreaderBookRow({ book }: KoreaderBookRowProps) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line-2 px-4 py-3.5 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate text-[14.5px] text-ink">{book.title}</p>
        <p className="mt-0.5 truncate text-[12.5px] text-ink-mute">
          {formatAuthors(book.authors)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-4">
        <p className="text-right text-[12.5px] tabular-nums text-ink-mute">
          {book.totalSessions} session{book.totalSessions > 1 ? "s" : ""}
          <br />
          {formatDuration(book.totalDurationSec)}
        </p>
        {book.matched ? (
          <span className="flex items-center gap-1.5 text-[13px] text-ink">
            <Check className="h-4 w-4" aria-hidden="true" />
            <span className="hidden @min-[480px]:inline">Rattaché</span>
          </span>
        ) : (
          <span className="text-[13px] text-ink-mute">À rattacher</span>
        )}
      </div>
    </div>
  )
}
