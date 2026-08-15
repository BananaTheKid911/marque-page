import { AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"

interface KoreaderErrorNoticeProps {
  message: string
  onRetry?: () => void
}

/**
 * État d'erreur (fichier invalide, trop volumineux, échec du parsing).
 *
 * AGENTS.md cite explicitement l'import KOReader comme candidat à une
 * future « couleur de signal », mais la décision n'est pas tranchée
 * (point ouvert, remonté à Jordy — voir rapport de session). En
 * attendant : uniquement les tokens d'encre. La distinction vient du
 * poids (bordure `border-ink` plus posée que le `border-line` habituel,
 * icône et label en gras) et du texte du label lui-même, jamais d'une
 * teinte. Le contraste avec le reste de l'écran suffit à signaler
 * l'anomalie sans qu'aucun rouge n'existe dans la palette.
 */
export function KoreaderErrorNotice({ message, onRetry }: KoreaderErrorNoticeProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-[4px] border border-ink bg-card px-4 py-4 @min-[420px]:flex-row @min-[420px]:items-center @min-[420px]:justify-between"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-ink" aria-hidden="true" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink">
            Import impossible
          </p>
          <p className="mt-1 text-[13.5px] text-ink-soft">{message}</p>
        </div>
      </div>
      {onRetry && (
        <Button
          type="button"
          variant="outline"
          size="default"
          className="shrink-0 rounded-[3px]"
          onClick={onRetry}
        >
          Réessayer
        </Button>
      )}
    </div>
  )
}
