import { useRef, useState } from "react"
import { Link } from "react-router-dom"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { SettingsSection } from "@/components/settings/SettingsSection"
import { SettingsRow } from "@/components/settings/SettingsRow"
import { formatDateLong } from "@/lib/format"
import { importBooktrack } from "@/lib/api"
import { useBooks } from "@/context/books"
import type { BooktrackImportResult } from "@/types/import"

/** Limite serveur du backend (backend/app/routers/booktrack.py) : 10 Mo. */
const MAX_BOOKTRACK_BYTES = 10 * 1024 * 1024

/**
 * Réglages. Écran "sans couverture" (AGENTS.md) — pas d'image, pas
 * d'accent. Seuls l'export et l'import Book Track sont réels ici (filet de
 * sûreté du NVMe : bouton "Exporter (ZIP)" ; migration depuis l'export CSV
 * Book Track) ; mot de passe (APP_PASSWORD), seuil SESSION_GAP_SEC et
 * KOReader restent inertes tant que l'auth et les réglages serveur ne
 * sont pas câblés. Aucun bouton n'est rempli d'encre : aucune action ne
 * domine vraiment les autres sur cet écran, la masse noire (réservée à UN
 * point de fixation par écran) n'est pas utilisée — tout reste en outline.
 */
export function SettingsPage() {
  const { notifyBooksChanged } = useBooks()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<BooktrackImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  // GET /api/v1/export sert le backup (Content-Disposition: attachment) :
  // un simple lien de navigation suffit, le navigateur télécharge l'archive.
  function handleExport() {
    window.location.href = "/api/v1/export"
  }

  function handleFileSelected(selected: File) {
    setError(null)
    setResult(null)
    // Mêmes gardes que le backend (extension + taille) : feedback immédiat
    // sans round-trip réseau, en plus du 422 serveur.
    if (!/\.csv$/i.test(selected.name)) {
      setFile(null)
      setError("Le fichier doit être un CSV (export Book Track).")
      return
    }
    if (selected.size > MAX_BOOKTRACK_BYTES) {
      setFile(null)
      setError("Fichier trop volumineux (max 10 Mo).")
      return
    }
    setFile(selected)
  }

  async function handleImport() {
    if (!file) return
    setBusy(true)
    setError(null)
    setResult(null)
    try {
      const res = await importBooktrack(file)
      setResult(res)
      // Des livres ont pu être créés : la bibliothèque et la carte
      // « En cours » doivent recharger leurs listes.
      notifyBooksChanged()
    } catch (err) {
      // ApiError.message porte déjà le `detail` FastAPI (422/413) ou le
      // message réseau (status 0).
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex max-w-2xl flex-col gap-8 pb-8">
      <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
        Réglages
      </h1>

      <SettingsSection title="Compte">
        <SettingsRow label="Mot de passe de l'application" hint="APP_PASSWORD, réseau Tailscale uniquement">
          <div className="flex w-full flex-col gap-2 @min-[420px]:w-auto @min-[420px]:flex-row">
            <Input
              type="password"
              placeholder="Nouveau mot de passe"
              className="w-full @min-[420px]:w-44"
            />
            <Button variant="outline" size="default" className="rounded-[3px]">
              Modifier
            </Button>
          </div>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection
        title="Préférences de lecture"
        description="Ces réglages ajustent la reconstruction des sessions à partir des imports KOReader."
      >
        <SettingsRow
          label="Seuil d'inactivité entre deux sessions"
          hint="Au-delà, KOReader considère qu'une nouvelle session commence"
        >
          <Select defaultValue="900">
            <SelectTrigger className="w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="300">5 min</SelectItem>
              <SelectItem value="600">10 min</SelectItem>
              <SelectItem value="900">15 min</SelectItem>
              <SelectItem value="1800">30 min</SelectItem>
              <SelectItem value="3600">1 h</SelectItem>
            </SelectContent>
          </Select>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection
        title="Import KOReader"
        description="Upload manuel du fichier statistics.sqlite3 — l'app propose un aperçu des sessions et highlights avant confirmation."
      >
        <SettingsRow label="Importer un fichier statistics.sqlite3">
          <Button asChild variant="outline" size="default" className="rounded-[3px]">
            <Link to="/reglages/import-koreader">Choisir un fichier</Link>
          </Button>
        </SettingsRow>
        <SettingsRow
          label="Dernier import"
          hint={`${formatDateLong("2026-08-12T19:20:00")} — 2 livres non rattachés à confirmer`}
        >
          <Link
            to="/reglages/import-koreader"
            className="text-[13px] font-medium text-ink underline underline-offset-2"
          >
            Rattacher
          </Link>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection
        title="Import Book Track"
        description="Migration depuis un export CSV de l'app Book Track (fichier booktracker.csv) — les livres déjà présents dans ta bibliothèque sont ignorés."
      >
        <SettingsRow
          label="Fichier CSV"
          hint={
            file
              ? `${file.name} — ${formatBytes(file.size)}`
              : "Export Book Track, colonnes d'origine"
          }
        >
          <div className="flex w-full flex-col gap-2 @min-[420px]:w-auto @min-[420px]:flex-row">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              className="sr-only"
              disabled={busy}
              onChange={(event) => {
                const selected = event.target.files?.[0]
                if (selected) handleFileSelected(selected)
                // Autorise de re-sélectionner le même fichier après une erreur.
                event.target.value = ""
              }}
              aria-label="Sélectionner le fichier CSV d'export Book Track"
            />
            <Button
              type="button"
              variant="outline"
              size="default"
              className="min-h-11 rounded-[3px]"
              disabled={busy}
              onClick={() => fileInputRef.current?.click()}
            >
              {file ? file.name : "Choisir un fichier"}
            </Button>
            <Button
              type="button"
              variant="outline"
              size="default"
              className="min-h-11 rounded-[3px]"
              disabled={busy || !file}
              onClick={handleImport}
            >
              {busy ? "Import en cours…" : "Importer"}
            </Button>
          </div>
        </SettingsRow>

        {result && (
          <SettingsRow label="Résultat">
            <div className="flex flex-col gap-1" aria-live="polite">
              {result.books_created === 0 ? (
                <p className="text-[14.5px] text-ink">
                  Aucun livre nouveau — export déjà importé
                </p>
              ) : (
                <p className="text-[14.5px] tabular-nums text-ink">
                  {result.books_created} livre{result.books_created > 1 ? "s" : ""} créé
                  {result.books_created > 1 ? "s" : ""}
                </p>
              )}
              {result.books_skipped > 0 && (
                <p className="text-[12.5px] tabular-nums text-ink-mute">
                  {result.books_skipped} déjà présent{result.books_skipped > 1 ? "s" : ""} (ignoré
                  {result.books_skipped > 1 ? "s" : ""})
                </p>
              )}
              {result.covers_downloaded > 0 && (
                <p className="text-[12.5px] tabular-nums text-ink-mute">
                  {result.covers_downloaded} couverture
                  {result.covers_downloaded > 1 ? "s" : ""} téléchargée
                  {result.covers_downloaded > 1 ? "s" : ""}
                </p>
              )}
              {result.covers_failed > 0 && (
                <p className="text-[12.5px] tabular-nums text-ink-mute">
                  {result.covers_failed} couverture{result.covers_failed > 1 ? "s" : ""} en échec
                  (best-effort)
                </p>
              )}
              {result.line_errors.length > 0 && (
                <div className="mt-1 flex flex-col gap-0.5">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
                    Lignes non importées
                  </p>
                  {result.line_errors.map(([line, reason]) => (
                    <p key={line} className="text-[12.5px] tabular-nums text-ink-mute">
                      Ligne {line} : {reason}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </SettingsRow>
        )}

        {error && (
          <SettingsRow label="Erreur">
            <p className="max-w-60 text-[13px] text-ink" aria-live="polite">
              {error}
            </p>
          </SettingsRow>
        )}
      </SettingsSection>

      <SettingsSection title="Sauvegarde">
        <SettingsRow
          label="Exporter mes données"
          hint="Archive ZIP complète — base et couvertures ne sont pas dans le backup 3-2-1"
        >
          <Button
            variant="outline"
            size="default"
            className="rounded-[3px]"
            onClick={handleExport}
          >
            Exporter (ZIP)
          </Button>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="À propos">
        <SettingsRow label="Version">
          <span className="text-[13px] tabular-nums text-ink-mute">0.1.0 — Phase 2</span>
        </SettingsRow>
        <SettingsRow label="Accès">
          <span className="text-[13px] text-ink-mute">Tailnet uniquement, aucun port public</span>
        </SettingsRow>
      </SettingsSection>
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(0)} Ko`
  return `${(kb / 1024).toFixed(1)} Mo`
}
