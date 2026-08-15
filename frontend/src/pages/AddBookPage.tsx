import { useRef, useState, type FormEvent } from "react"
import { Link } from "react-router-dom"
import { ChevronLeft, CircleCheck } from "lucide-react"
import { Button } from "@/components/ui/button"
import { AddModeTabs, type AddMode } from "@/components/add/AddModeTabs"
import { IsbnScanPanel, type ScanState } from "@/components/add/IsbnScanPanel"
import { TextSearchForm } from "@/components/add/TextSearchForm"
import { SearchResultsPanel, type SearchStatus } from "@/components/add/SearchResultsPanel"
import { CoverPicker } from "@/components/add/CoverPicker"
import { mockResultsFor } from "@/components/add/mock-results"
import type { SearchCandidate } from "@/components/add/types"

/**
 * Écran "Ajouter un livre" (spec §4) — un des écrans "sans couverture"
 * d'AGENTS.md tant qu'aucun résultat n'est choisi : pas d'image, la
 * hiérarchie tient aux onglets, au poids du texte et à un seul bouton
 * d'encre par étape.
 *
 * Trois étapes dans le même écran, pas trois routes : recherche → liste de
 * résultats → choix de couverture → confirmation. Le layout reste une
 * colonne unique à largeur contrainte (comme SettingsPage) : c'est un
 * flux de formulaire, pas une grille de contenu — @min-[…]: n'intervient
 * que dans la grille de couvertures (CoverPicker), pas dans la
 * composition d'ensemble.
 *
 * AUCUN appel réseau réel ici. `runMockSearch` simule les états de la
 * spec (chargement, erreur réseau, aucun résultat, résultats) avec des
 * délais artificiels et des déclencheurs de démo textuels — voir
 * mock-results.ts. Le scan caméra (zxing) n'est pas branché : `onStartScan`
 * simule juste l'état "scan en cours" puis "rien détecté".
 *
 * TODO frontend-dev :
 * - brancher zxing sur IsbnScanPanel (onStartScan/onCancelScan réels,
 *   detection → déclenche la recherche par ISBN au lieu de "not-detected")
 * - remplacer runMockSearch par l'appel API réel (contrat à définir)
 * - remplacer handleConfirm par la création réelle du livre (POST /books
 *   ou équivalent, à définir avec backend-dev) + téléchargement local de
 *   la couverture choisie (jamais de hotlink, AGENTS.md)
 */
export function AddBookPage() {
  const [mode, setMode] = useState<AddMode>("isbn")

  // --- scan ISBN (simulation) ---
  const [scanState, setScanState] = useState<ScanState>("idle")
  const scanTimeoutRef = useRef<number | null>(null)

  function handleStartScan() {
    setScanState("scanning")
    if (scanTimeoutRef.current) window.clearTimeout(scanTimeoutRef.current)
    // TODO frontend-dev : remplacer par l'ouverture réelle de la caméra (zxing)
    scanTimeoutRef.current = window.setTimeout(() => setScanState("not-detected"), 2200)
  }

  function handleCancelScan() {
    if (scanTimeoutRef.current) window.clearTimeout(scanTimeoutRef.current)
    setScanState("idle")
  }

  // --- saisie ---
  const [isbnValue, setIsbnValue] = useState("")
  const [titleValue, setTitleValue] = useState("")
  const [authorValue, setAuthorValue] = useState("")

  // --- recherche (mock) ---
  const [searchStatus, setSearchStatus] = useState<SearchStatus>("idle")
  const [results, setResults] = useState<SearchCandidate[]>([])
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null)
  const [selectedCoverId, setSelectedCoverId] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  function runMockSearch(query: string) {
    setSearchStatus("loading")
    setResults([])
    setSelectedCandidateId(null)
    window.setTimeout(() => {
      const q = query.trim().toLowerCase()
      if (q.includes("erreur")) {
        setSearchStatus("error")
        return
      }
      if (!q || q.includes("zzz")) {
        setSearchStatus("empty")
        return
      }
      setResults(mockResultsFor(query))
      setSearchStatus("done")
    }, 900)
  }

  function handleManualIsbnSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!isbnValue.trim()) return
    runMockSearch(isbnValue)
  }

  function handleTextSearchSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const query = [titleValue, authorValue].filter(Boolean).join(" ")
    if (!query.trim()) return
    runMockSearch(query)
  }

  function handleRetrySearch() {
    runMockSearch(mode === "isbn" ? isbnValue : `${titleValue} ${authorValue}`)
  }

  function handleSelectCandidate(candidate: SearchCandidate) {
    setSelectedCandidateId(candidate.id)
    setSelectedCoverId(candidate.covers[0]?.id ?? null)
  }

  function handleBackToResults() {
    setSelectedCandidateId(null)
    setSelectedCoverId(null)
  }

  function handleConfirm() {
    // TODO frontend-dev : appel réel de création + retour vers le livre créé
    setConfirmed(true)
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
        <CoverPicker
          candidate={selectedCandidate}
          selectedCoverId={selectedCoverId}
          onSelectCover={setSelectedCoverId}
          onConfirm={handleConfirm}
          onBack={handleBackToResults}
        />
      ) : (
        <div className="flex flex-col gap-6">
          <AddModeTabs mode={mode} onChange={setMode} />

          {mode === "isbn" ? (
            <IsbnScanPanel
              scanState={scanState}
              onStartScan={handleStartScan}
              onCancelScan={handleCancelScan}
              isbnValue={isbnValue}
              onIsbnChange={setIsbnValue}
              onManualSubmit={handleManualIsbnSubmit}
              disabled={searchStatus === "loading"}
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
