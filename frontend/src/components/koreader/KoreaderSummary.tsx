import { formatDuration } from "@/lib/format"
import type { KoreaderPreview } from "@/types/koreader"

interface KoreaderSummaryProps {
  preview: KoreaderPreview
  booksMatched: number
  booksUnmatched: number
}

/**
 * Résumé de l'aperçu. Le levier de hiérarchie ici est le poids/la taille
 * (AGENTS.md § « Hiérarchie sans couleur ») : le nombre de sessions à
 * importer domine à 34px, tout le reste — sessions ignorées, livres
 * rattachés/non rattachés — reste en 12,5-13px `ink-mute`. Aucune couleur
 * ne distingue "bien" de "à vérifier".
 */
export function KoreaderSummary({ preview, booksMatched, booksUnmatched }: KoreaderSummaryProps) {
  return (
    <div className="rounded-[4px] border border-line bg-card px-5 py-5">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-4">
        <div>
          <p className="text-[34px] font-semibold leading-none tabular-nums text-ink">
            {preview.sessionsToImport}
          </p>
          <p className="mt-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
            Session{preview.sessionsToImport > 1 ? "s" : ""} à importer
          </p>
        </div>

        <dl className="flex flex-1 flex-wrap gap-x-6 gap-y-2 text-[13px]">
          <div className="flex items-baseline gap-1.5">
            <dt className="text-ink-mute">Déjà importées</dt>
            <dd className="tabular-nums text-ink-soft">{preview.sessionsSkipped}</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-ink-mute">Livres rattachés</dt>
            <dd className="tabular-nums text-ink-soft">{booksMatched}</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-ink-mute">À rattacher</dt>
            <dd className="tabular-nums text-ink-soft">{booksUnmatched}</dd>
          </div>
          <div className="flex items-baseline gap-1.5">
            <dt className="text-ink-mute">Seuil d'inactivité</dt>
            <dd className="tabular-nums text-ink-soft">{formatDuration(preview.gapSec)}</dd>
          </div>
        </dl>
      </div>
    </div>
  )
}
