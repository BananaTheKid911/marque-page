import { useEffect, useRef, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { ChevronLeft, CircleCheck } from "lucide-react"
import {
  ApiError,
  createBook,
  lookupByIsbn,
  lookupByQuery,
  lookupCovers,
  type CoverVariantWire,
  type LookupCandidateWire,
  type LookupResultWire,
} from "@/lib/api"
import { useBooks } from "@/context/books"
import { useIsbnScanner } from "@/lib/use-isbn-scanner"
import { Button } from "@/components/ui/button"
import { AddModeTabs, type AddMode } from "@/components/add/AddModeTabs"
import { IsbnScanPanel, type ScanState } from "@/components/add/IsbnScanPanel"
import { TextSearchForm } from "@/components/add/TextSearchForm"
import { SearchResultsPanel, type SearchStatus } from "@/components/add/SearchResultsPanel"
import { CoverPicker } from "@/components/add/CoverPicker"
import type { CoverCandidate, SearchCandidate, SearchSource } from "@/components/add/types"

/**
 * Écran "Ajouter un livre" (spec §4) — câblé sur le backend réel :
 * GET /lookup?isbn= et GET /lookup?q= (recherche), GET /lookup/covers
 * (variantes à la sélection), POST /books (création — la couverture choisie
 * est téléchargée LOCALEMENT par le backend, jamais de hotlink, AGENTS.md).
 * Le scan ISBN passe par zxing (lib/use-isbn-scanner.ts) ; la caméra exige
 * un contexte sécurisé — voir la note dans ce hook.
 *
 * Trois étapes dans le même écran, pas trois routes : recherche → liste de
 * résultats → choix de couverture → confirmation.
 */
export function AddBookPage() {
  const { notifyBooksChanged } = useBooks()
  const [mode, setMode] = useState<AddMode>("isbn")

  // --- scan ISBN (zxing) ---
  const [scanState, setScanState] = useState<ScanState>("idle")
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const scanner = useIsbnScanner()

  // --- saisie ---
  const [isbnValue, setIsbnValue] = useState("")
  const [titleValue, setTitleValue] = useState("")
  const [authorValue, setAuthorValue] = useState("")

  // --- recherche (API réelle) ---
  const [searchStatus, setSearchStatus] = useState<SearchStatus>("idle")
  const [results, setResults] = useState<SearchCandidate[]>([])
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [selectedCoverId, setSelectedCoverId] = useState<string | null>(null)
  const [coversLoading, setCoversLoading] = useState(false)
  const [confirmed, setConfirmed] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Démarrage de la caméra quand le panneau de scan affiche la <video>.
  useEffect(() => {
    if (scanState !== "scanning") return
    const video = videoRef.current
    if (!video) return
    let cancelled = false
    scanner
      .start(video, (isbn) => {
        if (cancelled) return
        setScanState("idle")
        setIsbnValue(isbn)
        void runSearch(isbn, true)
      })
      .catch(() => {
        // Caméra refusée / indisponible (contexte non sécurisé, permission,
        // aucun appareil) : repli sur l'état dessiné + saisie manuelle.
        if (!cancelled) setScanState("not-detected")
      })
    return () => {
      cancelled = true
      scanner.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanState])

  async function runSearch(query: string, viaIsbn: boolean) {
    setSearchStatus("loading")
    setResults([])
    setSelectedCandidateId(null)
    setSelectedCoverId(null)
    setSubmitError(null)
    try {
      let mapped: SearchCandidate[]
      if (viaIsbn) {
        // Le lookup ISBN renvoie UN résultat avec ses variantes déjà là.
        const result = await lookupByIsbn(query)
        mapped = [toSearchCandidate(result, result.covers.map(mapVariant))]
      } else {
        // La recherche titre renvoie des candidats sans variantes (seul le
        // thumb est dispo) : elles seront chargées à la sélection.
        mapped = (await lookupByQuery(query)).map((c) => toSearchCandidate(c))
      }
      setResults(mapped)
      setSearchStatus(mapped.length > 0 ? "done" : "empty")
    } catch (err) {
      // ISBN inconnu (404) = « aucun résultat » ; tout le reste = panne.
      if (err instanceof ApiError && err.status === 404) setSearchStatus("empty")
      else setSearchStatus("error")
    }
  }

  function handleManualIsbnSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!isbnValue.trim() || searchStatus === "loading") return
    void runSearch(isbnValue.trim(), true)
  }

  function handleTextSearchSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const query = [titleValue, authorValue].filter(Boolean).join(" ")
    if (!query.trim() || searchStatus === "loading") return
    void runSearch(query, false)
  }

  function handleRetrySearch() {
    void runSearch(
      mode === "isbn" ? isbnValue.trim() : `${titleValue} ${authorValue}`.trim(),
      mode === "isbn",
    )
  }

  function handleSelectCandidate(candidate: SearchCandidate) {
    setSelectedCandidateId(candidate.id)
    setSelectedCoverId(null)
    if (candidate.covers.length > 0) {
      setSelectedCoverId(candidate.covers[0]?.id ?? null)
      return
    }
    // Variantes pas encore chargées : GET /lookup/covers pour ce candidat.
    setCoversLoading(true)
    lookupCovers(candidate.work, candidate.isbn)
      .then((variants) => {
        const covers = variants.map(mapVariant)
        setResults((prev) => prev.map((r) => (r.id === candidate.id ? { ...r, covers } : r)))
        setSelectedCoverId(covers[0]?.id ?? null)
      })
      .catch(() => {
        // Aucune variante (ou réseau) : le livre reste sélectionnable sans
        // couverture — BookCover gère déjà `coverUrl: null`.
        setResults((prev) => prev.map((r) => (r.id === candidate.id ? { ...r, covers: [] } : r)))
        setSelectedCoverId(null)
      })
      .finally(() => setCoversLoading(false))
  }

  function handleBackToResults() {
    setSelectedCandidateId(null)
    setSelectedCoverId(null)
  }

  async function handleConfirm() {
    if (!selectedCandidate || submitting) return
    const cover = selectedCandidate.covers.find((c) => c.id === selectedCoverId) ?? null
    setSubmitting(true)
    setSubmitError(null)
    try {
      await createBook({
        title: selectedCandidate.title,
        subtitle: selectedCandidate.subtitle ?? null,
        authors: selectedCandidate.authors,
        publisher: selectedCandidate.publisher ?? null,
        published_date: selectedCandidate.publishedDate ?? null,
        page_count: selectedCandidate.pageCount ?? null,
        language: selectedCandidate.language ?? null,
        description: selectedCandidate.description ?? null,
        isbn10: isbn10(selectedCandidate.isbn),
        isbn13: isbn13(selectedCandidate.isbn),
        cover_url: cover?.url ?? null,
        cover_source: cover ? (cover.source === "google_books" ? "google" : "openlibrary") : null,
      })
      notifyBooksChanged()
      setConfirmed(true)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  function handleAddAnother() {
    setConfirmed(false)
    setSelectedCandidateId(null)
    setSelectedCoverId(null)
    setSearchStatus("idle")
    setResults([])
    setIsbnValue("")
    setTitleValue("")
    setAuthorValue("")
    setScanState("idle")
    setSubmitError(null)
  }

  const selectedCandidate = results.find((r) => r.id === selectedCandidateId) ?? null

  return (
    <div className="flex max-w-2xl flex-col gap-6 pb-8">
      <Link
        to="/"
        className="inline-flex w-fit items-center gap-1 text-[13.5px] text-ink-mute transition-colors hover:text-ink"
      >
        <ChevronLeft className="h-4 w-4" aria-hidden="true" />
        Bibliothèque
      </Link>

      <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
        Ajouter un livre
      </h1>

      {confirmed ? (
        <div className="flex flex-col items-center gap-4 py-16 text-center">
          <CircleCheck className="h-9 w-9 text-ink" strokeWidth={1.5} aria-hidden="true" />
          <div>
            <h2 className="text-[17px] font-semibold text-ink">Livre ajouté</h2>
            <p className="mx-auto mt-1.5 max-w-[36ch] text-[13.5px] text-ink-mute">
              {selectedCandidate?.title ?? "Le livre"} vient d'être ajouté à ta bibliothèque.
            </p>
          </div>
          <div className="flex gap-3">
            <Button
              type="button"
              variant="outline"
              onClick={handleAddAnother}
              className="h-11 rounded-[3px] px-5 text-[15px]"
            >
              Ajouter un autre livre
            </Button>
            <Button asChild className="h-11 rounded-[3px] px-5 text-[15px]">
              <Link to="/">Retour à la bibliothèque</Link>
            </Button>
          </div>
        </div>
      ) : selectedCandidate ? (
        <>
          <CoverPicker
            candidate={selectedCandidate}
            selectedCoverId={selectedCoverId}
            onSelectCover={setSelectedCoverId}
            onConfirm={handleConfirm}
            onBack={handleBackToResults}
            submitting={submitting || coversLoading}
          />
          {submitError && (
            <p className="text-[12.5px] text-ink-soft" role="alert">
              {submitError}
            </p>
          )}
        </>
      ) : (
        <div className="flex flex-col gap-6">
          <AddModeTabs mode={mode} onChange={setMode} />

          {mode === "isbn" ? (
            <IsbnScanPanel
              scanState={scanState}
              onStartScan={() => setScanState("scanning")}
              onCancelScan={() => setScanState("idle")}
              isbnValue={isbnValue}
              onIsbnChange={setIsbnValue}
              onManualSubmit={handleManualIsbnSubmit}
              disabled={searchStatus === "loading"}
              videoRef={videoRef}
            />
          ) : (
            <TextSearchForm
              titleValue={titleValue}
              onTitleChange={setTitleValue}
              authorValue={authorValue}
              onAuthorChange={setAuthorValue}
              onSubmit={handleTextSearchSubmit}
              disabled={searchStatus === "loading"}
            />
          )}

          <SearchResultsPanel
            status={searchStatus}
            results={results}
            onSelect={handleSelectCandidate}
            onRetry={handleRetrySearch}
          />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Mappers lookup → formes de l'UI (components/add/types.ts)
// ---------------------------------------------------------------------------

const SOURCE_MAP: Record<string, SearchSource> = {
  openlibrary: "openlibrary",
  google: "google_books",
}

function mapSource(source: string): SearchSource {
  return SOURCE_MAP[source] ?? "openlibrary"
}

function candidateId(c: {
  openlibrary_work: string | null
  openlibrary_edition: string | null
  google_books_id: string | null
  isbn13: string | null
  isbn10: string | null
  title: string
}): string {
  return (
    c.openlibrary_work ??
    c.openlibrary_edition ??
    c.google_books_id ??
    c.isbn13 ??
    c.isbn10 ??
    `cand-${c.title}`
  )
}

function mapVariant(v: CoverVariantWire): CoverCandidate {
  const dims = v.width != null && v.height != null ? `${v.width}×${v.height}` : ""
  const resolution =
    v.width != null
      ? v.width >= 500
        ? "grande résolution"
        : v.width >= 250
          ? "résolution moyenne"
          : "petite résolution"
      : ""
  const label = [dims, resolution].filter(Boolean).join(" — ")
  return {
    id: v.url,
    url: v.url,
    source: mapSource(v.source),
    label: label || "Couverture",
    hasImage: true,
  }
}

function toSearchCandidate(
  c: LookupCandidateWire | LookupResultWire,
  covers: CoverCandidate[] = [],
): SearchCandidate {
  return {
    id: candidateId(c),
    title: c.title,
    subtitle: c.subtitle,
    authors: c.authors,
    publisher: c.publisher,
    publishedDate: c.published_date,
    isbn: c.isbn13 ?? c.isbn10,
    work: c.openlibrary_work,
    pageCount: c.page_count,
    language: c.language,
    description: c.description,
    source: mapSource(c.source),
    covers,
  }
}

/** ISBN-10 seul (10 caractères), sinon null — la création les sépare. */
function isbn10(value: string | null | undefined): string | null {
  const clean = (value ?? "").replace(/\s/g, "")
  return clean.length === 10 ? clean : null
}

function isbn13(value: string | null | undefined): string | null {
  const clean = (value ?? "").replace(/\s/g, "")
  return clean.length === 13 ? clean : null
}
