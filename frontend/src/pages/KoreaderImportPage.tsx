import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { ChevronLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { KoreaderDropzone } from "@/components/koreader/KoreaderDropzone"
import { KoreaderErrorNotice } from "@/components/koreader/KoreaderErrorNotice"
import { KoreaderSummary } from "@/components/koreader/KoreaderSummary"
import { KoreaderBookRow } from "@/components/koreader/KoreaderBookRow"
import { KoreaderMatchCard } from "@/components/koreader/KoreaderMatchCard"
import { KoreaderResult } from "@/components/koreader/KoreaderResult"
import type { KoreaderConfirmResult, KoreaderMapping, KoreaderPreview } from "@/types/koreader"

/**
 * Import KOReader (§4.3 SPEC.md) — écran "sans couverture" (AGENTS.md).
 * Flux en trois temps porté par le backend (backend/app/routers/koreader.py) :
 * upload → aperçu (diff, matching auto par MD5 + candidats flous) →
 * confirmation. Ici : un seul stepper local, pas trois routes séparées —
 * `import_id` et les rattachements choisis n'ont besoin de survivre qu'à
 * la session de navigation, pas à un rechargement de page.
 *
 * PAS de réseau réel : `simulateUpload`/`simulateConfirm` sont des stubs
 * (setTimeout + données mock) que frontend-dev remplacera par
 * `uploadKoreaderFile`/`confirmKoreaderImport` dans lib/api.ts. Les
 * formes de données (KoreaderPreview, KoreaderConfirmResult) sont
 * calquées sur le contrat réel — seul le transport est faux.
 */

type Step = "upload" | "analyzing" | "error" | "preview" | "matching" | "confirming" | "result"

const MAX_BYTES = 50 * 1024 * 1024

// --- Mock représentatif d'un KoreaderPreview (backend/app/schemas.py) ---
const MOCK_PREVIEW: KoreaderPreview = {
  importId: "6f2c9a1e4b8d7c3f5a0e9d2b1c4f6a8e3d5b7c9f1a2e4d6b8c0f2a4e6d8b0c1f",
  gapSec: 900,
  sessionsToImport: 41,
  sessionsSkipped: 6,
  books: [
    {
      koreaderBookId: 101,
      title: "Les Furtifs",
      authors: ["Alain Damasio"],
      md5: "a1b2c3d4",
      totalSessions: 14,
      totalDurationSec: 30240,
      matched: true,
      matchedBookId: 5,
      candidates: [],
    },
    {
      koreaderBookId: 102,
      title: "Providence",
      authors: ["Alain Damasio"],
      md5: "e5f6a7b8",
      totalSessions: 6,
      totalDurationSec: 9600,
      matched: true,
      matchedBookId: 12,
      candidates: [],
    },
    {
      koreaderBookId: 103,
      title: "La Horde du Contrevent",
      authors: ["Alain Damasio"],
      md5: "c9d0e1f2",
      totalSessions: 22,
      totalDurationSec: 54000,
      matched: false,
      matchedBookId: null,
      candidates: [
        { bookId: 7, title: "La Horde du Contrevent", authors: ["Alain Damasio"], score: 0.97 },
        { bookId: 9, title: "Le Contrevent, tome 1", authors: ["A. Damasio"], score: 0.71 },
      ],
    },
    {
      koreaderBookId: 104,
      title: "Dune - Tome 2",
      authors: ["Frank Herbert"],
      md5: "f3a4b5c6",
      totalSessions: 3,
      totalDurationSec: 5400,
      matched: false,
      matchedBookId: null,
      candidates: [
        { bookId: 15, title: "Le Messie de Dune", authors: ["Frank Herbert"], score: 0.58 },
      ],
    },
    {
      koreaderBookId: 105,
      title: "Un livre totalement inconnu",
      authors: ["Anonyme"],
      md5: "d7e8f9a0",
      totalSessions: 1,
      totalDurationSec: 720,
      matched: false,
      matchedBookId: null,
      candidates: [],
    },
  ],
  sessions: [],
}

/** Stub d'upload : valide localement, puis simule l'aller-retour réseau. */
function simulateUpload(file: File): Promise<KoreaderPreview> {
  return new Promise((resolve, reject) => {
    setTimeout(() => {
      // Démo de l'état d'erreur (fichier corrompu / non reconnu par le
      // parser) sans backend réel : un nom de fichier contenant "invalid".
      if (file.name.toLowerCase().includes("invalid")) {
        reject(new Error("Fichier SQLite illisible ou table `page_stat_data` absente."))
        return
      }
      resolve(MOCK_PREVIEW)
    }, 900)
  })
}

/** Stub de confirmation : ignore les mappings réels, renvoie un résultat mock cohérent. */
function simulateConfirm(mappings: KoreaderMapping[]): Promise<KoreaderConfirmResult> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        importId: MOCK_PREVIEW.importId,
        sessionsAdded: MOCK_PREVIEW.sessionsToImport,
        sessionsSkipped: MOCK_PREVIEW.sessionsSkipped,
        booksMatched: MOCK_PREVIEW.books.filter((b) => b.matched).length + mappings.length,
        booksUnmatched: MOCK_PREVIEW.books.filter((b) => !b.matched).length - mappings.length,
      })
    }, 700)
  })
}

export function KoreaderImportPage() {
  const [step, setStep] = useState<Step>("upload")
  const [file, setFile] = useState<File | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [preview, setPreview] = useState<KoreaderPreview | null>(null)
  const [mappings, setMappings] = useState<Record<number, number | null>>({})
  const [result, setResult] = useState<KoreaderConfirmResult | null>(null)

  useEffect(() => {
    if (step !== "analyzing" || !file) return
    let cancelled = false
    simulateUpload(file)
      .then((data) => {
        if (cancelled) return
        setPreview(data)
        setMappings(
          Object.fromEntries(
            data.books.filter((b) => !b.matched).map((b) => [b.koreaderBookId, null]),
          ),
        )
        setStep("preview")
      })
      .catch((err: Error) => {
        if (cancelled) return
        setErrorMessage(err.message)
        setStep("error")
      })
    return () => {
      cancelled = true
    }
  }, [step, file])

  function handleFileSelected(selected: File) {
    setErrorMessage(null)
    if (!/\.(sqlite3|sqlite|db)$/i.test(selected.name)) {
      setFile(null)
      setErrorMessage("Le fichier doit être une base SQLite (statistics.sqlite3).")
      setStep("error")
      return
    }
    if (selected.size > MAX_BYTES) {
      setFile(null)
      setErrorMessage("Fichier trop volumineux (max 50 Mo).")
      setStep("error")
      return
    }
    setFile(selected)
  }

  function reset() {
    setStep("upload")
    setFile(null)
    setErrorMessage(null)
    setPreview(null)
    setMappings({})
    setResult(null)
  }

  const unmatchedCount = preview?.books.filter((b) => !b.matched).length ?? 0
  const matchedCount = preview ? preview.books.length - unmatchedCount : 0

  async function handleConfirm() {
    setStep("confirming")
    const chosen: KoreaderMapping[] = Object.entries(mappings)
      .filter(([, bookId]) => bookId !== null)
      .map(([koreaderBookId, bookId]) => ({
        koreaderBookId: Number(koreaderBookId),
        bookId: bookId as number,
      }))
    const confirmResult = await simulateConfirm(chosen)
    setResult(confirmResult)
    setStep("result")
  }

  return (
    <div className="flex max-w-2xl flex-col gap-6 pb-8">
      <Link
        to="/reglages"
        className="inline-flex items-center gap-1 text-[13.5px] text-ink-mute hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Réglages
      </Link>

      <div>
        <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
          Import KOReader
        </p>
        <h1 className="mt-1 text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
          {stepTitle(step)}
        </h1>
      </div>

      {step === "upload" && (
        <div className="flex flex-col gap-4">
          <p className="text-[13.5px] text-ink-soft">
            Sélectionne le fichier <span className="font-medium">statistics.sqlite3</span> de
            ton appareil KOReader. Rien n'est écrit en base avant la confirmation finale — tu
            peux annuler à tout moment.
          </p>
          <KoreaderDropzone file={file} onFileSelected={handleFileSelected} />
          <Button
            type="button"
            variant="default"
            size="default"
            className="w-full rounded-[3px] @min-[420px]:w-fit"
            disabled={!file}
            onClick={() => setStep("analyzing")}
          >
            Lancer l'analyse
          </Button>
        </div>
      )}

      {step === "analyzing" && (
        <div
          className="flex flex-col items-center gap-3 rounded-[4px] border border-line bg-card px-6 py-14 text-center"
          aria-live="polite"
        >
          <div
            className="h-6 w-6 rounded-full border-2 border-line border-t-ink motion-safe:animate-spin"
            aria-hidden="true"
          />
          <p className="text-[13.5px] text-ink-soft">
            Analyse de {file?.name} en cours…
          </p>
        </div>
      )}

      {step === "error" && (
        <KoreaderErrorNotice
          message={errorMessage ?? "Une erreur inattendue est survenue."}
          onRetry={reset}
        />
      )}

      {step === "preview" && preview && (
        <div className="flex flex-col gap-5">
          <KoreaderSummary
            preview={preview}
            booksMatched={matchedCount}
            booksUnmatched={unmatchedCount}
          />

          <div className="rounded-[4px] border border-line bg-card">
            {preview.books.map((book) => (
              <KoreaderBookRow key={book.koreaderBookId} book={book} />
            ))}
          </div>

          <div className="flex flex-col gap-2 @min-[420px]:flex-row">
            <Button
              type="button"
              variant="default"
              size="default"
              className="rounded-[3px]"
              onClick={() => setStep(unmatchedCount > 0 ? "matching" : "confirming")}
            >
              {unmatchedCount > 0
                ? `Rattacher ${unmatchedCount} livre${unmatchedCount > 1 ? "s" : ""}`
                : "Confirmer l'import"}
            </Button>
            <Button type="button" variant="outline" size="default" className="rounded-[3px]" onClick={reset}>
              Annuler
            </Button>
          </div>
        </div>
      )}

      {step === "matching" && preview && (
        <div className="flex flex-col gap-5">
          <p className="text-[13.5px] text-ink-soft">
            {unmatchedCount} livre{unmatchedCount > 1 ? "s" : ""} sans correspondance exacte.
            Choisis un candidat suggéré ou ignore le livre — il pourra être rattaché
            manuellement plus tard, depuis la fiche du livre.
          </p>

          <div className="flex flex-col gap-4">
            {preview.books
              .filter((b) => !b.matched)
              .map((book) => (
                <KoreaderMatchCard
                  key={book.koreaderBookId}
                  book={book}
                  selectedBookId={mappings[book.koreaderBookId] ?? null}
                  onSelect={(bookId) =>
                    setMappings((prev) => ({ ...prev, [book.koreaderBookId]: bookId }))
                  }
                />
              ))}
          </div>

          <div className="flex flex-col gap-2 @min-[420px]:flex-row">
            <Button
              type="button"
              variant="default"
              size="default"
              className="rounded-[3px]"
              onClick={handleConfirm}
            >
              Valider les rattachements
            </Button>
            <Button
              type="button"
              variant="outline"
              size="default"
              className="rounded-[3px]"
              onClick={() => setStep("preview")}
            >
              Retour à l'aperçu
            </Button>
          </div>
        </div>
      )}

      {step === "confirming" && (
        <div
          className="flex flex-col items-center gap-3 rounded-[4px] border border-line bg-card px-6 py-14 text-center"
          aria-live="polite"
        >
          <div
            className="h-6 w-6 rounded-full border-2 border-line border-t-ink motion-safe:animate-spin"
            aria-hidden="true"
          />
          <p className="text-[13.5px] text-ink-soft">Écriture des sessions en base…</p>
        </div>
      )}

      {step === "result" && result && (
        <div className="flex flex-col gap-5">
          <KoreaderResult result={result} />
          <div className="flex flex-col gap-2 @min-[420px]:flex-row">
            <Button asChild variant="default" size="default" className="rounded-[3px]">
              <Link to="/reglages">Retour aux réglages</Link>
            </Button>
            <Button asChild variant="outline" size="default" className="rounded-[3px]">
              <Link to="/">Voir la bibliothèque</Link>
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function stepTitle(step: Step): string {
  switch (step) {
    case "upload":
      return "Importer un fichier"
    case "analyzing":
      return "Analyse en cours"
    case "error":
      return "Import impossible"
    case "preview":
      return "Aperçu de l'import"
    case "matching":
      return "Livres non rattachés"
    case "confirming":
      return "Confirmation"
    case "result":
      return "Import terminé"
  }
}
