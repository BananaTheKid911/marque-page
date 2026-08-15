import type { FormEvent, RefObject } from "react"
import { Camera, ScanLine, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export type ScanState = "idle" | "scanning" | "not-detected"

interface IsbnScanPanelProps {
  scanState: ScanState
  onStartScan: () => void
  onCancelScan: () => void
  isbnValue: string
  onIsbnChange: (value: string) => void
  onManualSubmit: (e: FormEvent<HTMLFormElement>) => void
  disabled?: boolean
  /**
   * Flux caméra branché par AddBookPage (zxing) : la zone de visée du
   * design devient un vrai <video> quand on scanne, la ligne et le cadre
   * restent par-dessus. `playsInline` est requis par iOS Safari.
   */
  videoRef?: RefObject<HTMLVideoElement | null>
}

/**
 * Scan caméra + saisie manuelle d'ISBN — deux voies indépendantes vers la
 * même recherche, pas l'une en repli de l'autre (spec §4 les liste comme
 * deux capacités distinctes). Le flux caméra réel est piloté par l'appelant
 * via `videoRef` : le composant ne possède pas la caméra, il l'affiche.
 */
export function IsbnScanPanel({
  scanState,
  onStartScan,
  onCancelScan,
  isbnValue,
  onIsbnChange,
  onManualSubmit,
  disabled,
  videoRef,
}: IsbnScanPanelProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col items-center gap-3 rounded-[4px] border border-line bg-card px-4 py-8 text-center">
        {scanState === "idle" && (
          <>
            <Camera className="h-8 w-8 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
            <div>
              <p className="text-[14.5px] text-ink">Scanner le code-barres du livre</p>
              <p className="mt-1 text-[12.5px] text-ink-mute">
                ISBN au dos de la couverture, généralement sous le code-barres
              </p>
            </div>
            <Button
              type="button"
              onClick={onStartScan}
              disabled={disabled}
              className="mt-1 h-11 rounded-[3px] px-5 text-[15px]"
            >
              <ScanLine className="h-4 w-4" aria-hidden="true" />
              Scanner un code-barres
            </Button>
          </>
        )}

        {scanState === "scanning" && (
          <>
            <div className="relative flex h-28 w-full max-w-56 items-center justify-center overflow-hidden rounded-[3px] bg-ink/90">
              <video
                ref={videoRef}
                playsInline
                muted
                className="absolute inset-0 h-full w-full object-cover"
                aria-label="Flux caméra pour le scan du code-barres"
              />
              <div className="absolute inset-3 rounded-[2px] border border-paper/50" aria-hidden="true" />
              <div
                className="absolute inset-x-3 h-px bg-paper/70 motion-safe:animate-pulse"
                aria-hidden="true"
              />
              <ScanLine className="h-6 w-6 text-paper/60" strokeWidth={1.5} aria-hidden="true" />
            </div>
            <p className="text-[13.5px] text-ink-soft" role="status">
              Recherche du code-barres…
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={onCancelScan}
              className="h-9 rounded-[3px] px-4 text-[13.5px]"
            >
              <X className="h-3.5 w-3.5" aria-hidden="true" />
              Annuler
            </Button>
          </>
        )}

        {scanState === "not-detected" && (
          <>
            <ScanLine className="h-8 w-8 text-ink-mute" strokeWidth={1.5} aria-hidden="true" />
            <div>
              <p className="text-[14.5px] text-ink">Aucun code-barres détecté</p>
              <p className="mt-1 text-[12.5px] text-ink-mute">
                Rapproche la caméra du code-barres, ou saisis l'ISBN ci-dessous
              </p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={onStartScan}
              disabled={disabled}
              className="mt-1 h-10 rounded-[3px] px-4 text-[14px]"
            >
              Réessayer
            </Button>
          </>
        )}
      </div>

      <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.16em] text-ink-mute">
        <span className="h-px flex-1 bg-line-2" aria-hidden="true" />
        ou saisir l'ISBN
        <span className="h-px flex-1 bg-line-2" aria-hidden="true" />
      </div>

      <form onSubmit={onManualSubmit} className="flex flex-col gap-2 @min-[420px]:flex-row">
        <Input
          type="text"
          inputMode="numeric"
          placeholder="978…"
          aria-label="ISBN"
          value={isbnValue}
          onChange={(e) => onIsbnChange(e.target.value)}
          className="h-11 rounded-[3px] text-[15px]"
        />
        <Button
          type="submit"
          variant="outline"
          disabled={disabled || isbnValue.trim().length === 0}
          className="h-11 shrink-0 rounded-[3px] px-5 text-[15px]"
        >
          Rechercher
        </Button>
      </form>
    </div>
  )
}

