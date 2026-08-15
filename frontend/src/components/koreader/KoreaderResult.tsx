import type { KoreaderConfirmResult } from "@/types/koreader"

interface KoreaderResultProps {
  result: KoreaderConfirmResult
}

/**
 * Écran de confirmation finale. Même logique de hiérarchie que
 * `KoreaderSummary` : le nombre de sessions ajoutées domine par la
 * taille, le reste (ignorées, livres rattachés/non rattachés) reste en
 * texte discret. Pas de pastille de succès colorée — la masse noire est
 * réservée au CTA de sortie.
 */
export function KoreaderResult({ result }: KoreaderResultProps) {
  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-[4px] border border-line bg-card px-5 py-6 text-center">
        <p className="text-[34px] font-semibold leading-none tabular-nums text-ink">
          {result.sessionsAdded}
        </p>
        <p className="mt-1.5 text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
          Session{result.sessionsAdded > 1 ? "s" : ""} ajoutée
          {result.sessionsAdded > 1 ? "s" : ""}
        </p>
      </div>

      <dl className="grid grid-cols-3 gap-4 text-center">
        <div>
          <dd className="text-[19px] font-medium tabular-nums text-ink">
            {result.sessionsSkipped}
          </dd>
          <dt className="mt-1 text-[12px] text-ink-mute">Déjà présentes</dt>
        </div>
        <div>
          <dd className="text-[19px] font-medium tabular-nums text-ink">
            {result.booksMatched}
          </dd>
          <dt className="mt-1 text-[12px] text-ink-mute">Livres rattachés</dt>
        </div>
        <div>
          <dd className="text-[19px] font-medium tabular-nums text-ink">
            {result.booksUnmatched}
          </dd>
          <dt className="mt-1 text-[12px] text-ink-mute">Non rattachés</dt>
        </div>
      </dl>
    </div>
  )
}
