import { useRef, useState, type DragEvent } from "react"
import { FileUp, UploadCloud } from "lucide-react"
import { cn } from "@/lib/utils"

interface KoreaderDropzoneProps {
  file: File | null
  onFileSelected: (file: File) => void
  disabled?: boolean
}

/**
 * Zone de dépôt/sélection du `statistics.sqlite3`. Pas de couleur d'état
 * « survol de drop » — seul le poids de la bordure change
 * (`border-line` → `border-ink`, en pointillés dans les deux cas pour
 * rester lisible comme une zone, pas un champ de formulaire classique).
 * Cible tactile large : toute la zone est cliquable, pas juste un bouton
 * interne.
 */
export function KoreaderDropzone({ file, onFileSelected, disabled }: KoreaderDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragging(false)
    if (disabled) return
    const dropped = event.dataTransfer.files?.[0]
    if (dropped) onFileSelected(dropped)
  }

  return (
    <div
      className={cn(
        "flex min-h-[188px] flex-col items-center justify-center gap-3 rounded-[4px] border-2 border-dashed px-6 py-10 text-center transition-colors",
        dragging ? "border-ink" : "border-line",
        disabled && "pointer-events-none opacity-50",
      )}
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      {file ? (
        <>
          <FileUp className="h-6 w-6 text-ink" aria-hidden="true" />
          <div>
            <p className="text-[14.5px] text-ink">{file.name}</p>
            <p className="mt-0.5 text-[12.5px] tabular-nums text-ink-mute">
              {formatBytes(file.size)}
            </p>
          </div>
          <button
            type="button"
            className="text-[13px] text-ink-mute underline underline-offset-2 hover:text-ink"
            onClick={() => inputRef.current?.click()}
            disabled={disabled}
          >
            Choisir un autre fichier
          </button>
        </>
      ) : (
        <>
          <UploadCloud className="h-6 w-6 text-ink-mute" aria-hidden="true" />
          <div>
            <p className="text-[14.5px] text-ink">
              Dépose ton fichier{" "}
              <span className="font-medium">statistics.sqlite3</span>
            </p>
            <p className="mt-1 text-[12.5px] text-ink-mute">
              ou{" "}
              <button
                type="button"
                className="text-ink underline underline-offset-2"
                onClick={() => inputRef.current?.click()}
                disabled={disabled}
              >
                parcourir
              </button>{" "}
              — 50 Mo maximum
            </p>
          </div>
        </>
      )}
      <input
        ref={inputRef}
        type="file"
        accept=".sqlite3,.sqlite,.db"
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          const selected = event.target.files?.[0]
          if (selected) onFileSelected(selected)
          // Autorise de re-sélectionner le même fichier après une erreur.
          event.target.value = ""
        }}
        aria-label="Sélectionner le fichier statistics.sqlite3"
      />
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(0)} Ko`
  return `${(kb / 1024).toFixed(1)} Mo`
}
