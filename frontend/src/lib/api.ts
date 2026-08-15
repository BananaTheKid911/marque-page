/**
 * Client HTTP de l'API Marque-page — le SEUL endroit qui appelle le réseau.
 *
 * Contrat réel : backend/app/schemas.py + routers/ (§5 de SPEC.md).
 * Préfixe relatif `/api/v1` : le backend sert le build statique et l'API
 * depuis la même origine — jamais d'URL absolue, jamais de CORS.
 *
 * Toutes les réponses passent par un mapper snake_case → camelCase pour
 * produire les types frontend (types/book.ts). Si le payload réel diverge
 * du contrat, le mapper échoue à la compilation OU une erreur de validation
 * est levée ici — à signaler à backend-dev plutôt que de contourner.
 */

import type {
  Author,
  Book,
  BookFormat,
  BookList,
  BookStatus,
  Highlight,
  HighlightList,
  Label,
  ReadingSession,
  Series,
  SeriesBooks,
  SessionList,
} from "@/types/book"

const API_BASE = "/api/v1"

// ---------------------------------------------------------------------------
// Erreurs
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number
  /** `detail` de FastAPI : string, ou liste d'erreurs de validation. */
  readonly detail: unknown

  constructor(status: number, detail: unknown) {
    super(formatDetail(status, detail))
    this.name = "ApiError"
    this.status = status
    this.detail = detail
  }
}

function formatDetail(status: number, detail: unknown): string {
  if (typeof detail === "string" && detail.length > 0) return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e: { loc?: unknown[]; msg?: unknown }) => `${e.loc?.slice(1).join(".")} : ${e.msg}`)
      .join(" ; ")
  }
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail)
    } catch {
      /* noop */
    }
  }
  return `Requête échouée (HTTP ${status})`
}

// ---------------------------------------------------------------------------
// Transport
// ---------------------------------------------------------------------------

interface RequestOptions {
  method?: string
  body?: unknown
  signal?: AbortSignal
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      signal,
      headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    // fetch ne rejette que sur erreur réseau (offline, serveur down).
    throw new ApiError(0, "Impossible de joindre le serveur — réseau ou backend injoignable")
  }
  if (!res.ok) {
    let detail: unknown = res.statusText
    try {
      const json = (await res.json()) as { detail?: unknown }
      if (json && "detail" in json) detail = json.detail
    } catch {
      /* corps non-JSON : garder statusText */
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function queryString(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue
    search.set(key, String(value))
  }
  const s = search.toString()
  return s ? `?${s}` : ""
}

// ---------------------------------------------------------------------------
// Types filaires (réponses BookOut / payloads snake_case)
// ---------------------------------------------------------------------------

interface BookOutWire {
  id: number
  title: string
  subtitle: string | null
  authors: string[]
  tags: string[]
  genres: string[]
  series_id: number | null
  series_name: string | null
  series_index: number | null
  formats: { type: BookFormat["type"]; owned: boolean }[]
  isbn10: string | null
  isbn13: string | null
  publisher: string | null
  published_date: string | null
  page_count: number | null
  language: string | null
  description: string | null
  cover_path: string | null
  cover_source: string | null
  cover_url: string | null
  cover_thumb_url: string | null
  status: string
  owned: number
  rating: number | null
  current_page: number
  current_percent: number
  acquired_date: string | null
  price_paid: number | null
  purchased_at: string | null
  is_primary_reading: boolean
  tbr_rank: number | null
  tbr_note: string | null
  created_at: string
  updated_at: string
}

interface ReadingSessionWire {
  id: number
  book_id: number
  started_at: string
  ended_at: string | null
  duration_sec: number
  start_page: number | null
  end_page: number | null
  pages_read: number | null
  note: string | null
  source: string
  koreader_hash: string | null
  created_at: string
}

interface HighlightWire {
  id: number
  book_id: number
  book_title: string | null
  text: string
  note: string | null
  page: number | null
  location: string | null
  chapter: string | null
  color: string | null
  source: string
  highlighted_at: string | null
  created_at: string
}

/** PATCH /books/{id} — champs snake_case, identiques à `BookUpdate`. */
export interface BookUpdatePayload {
  title?: string
  subtitle?: string | null
  authors?: string[]
  tags?: string[]
  genres?: string[]
  /** nom upserté ; "" = retirer la série ; `null`/absent = ne pas toucher */
  series?: string | null
  series_index?: number | null
  formats?: BookFormat[]
  publisher?: string | null
  published_date?: string | null
  page_count?: number | null
  language?: string | null
  description?: string | null
  status?: BookStatus
  rating?: number | null
  current_page?: number
  acquired_date?: string | null
  price_paid?: number | null
  purchased_at?: string | null
  is_primary_reading?: boolean
  tbr_rank?: number | null
  tbr_note?: string | null
  notes?: string | null
}

export interface BooksQuery {
  status?: BookStatus
  tag?: string
  genre?: string
  author?: string
  owned?: 0 | 1
  q?: string
  sort?: "title" | "created" | "rating" | "tbr_rank"
  page?: number
  page_size?: number
}

// ---------------------------------------------------------------------------
// Mappers snake_case → camelCase
// ---------------------------------------------------------------------------

function mapBook(out: BookOutWire): Book {
  return {
    id: out.id,
    title: out.title,
    subtitle: out.subtitle ?? null,
    authors: out.authors,
    tags: out.tags,
    genres: out.genres,
    status: out.status as BookStatus,
    coverUrl: out.cover_url,
    coverThumbUrl: out.cover_thumb_url,
    pageCount: out.page_count,
    currentPage: out.current_page,
    currentPercent: out.current_percent,
    rating: out.rating,
    publisher: out.publisher,
    publishedDate: out.published_date,
    language: out.language,
    description: out.description,
    owned: out.owned === 1,
    isPrimaryReading: Boolean(out.is_primary_reading),
    seriesId: out.series_id,
    seriesName: out.series_name,
    seriesIndex: out.series_index,
    formats: out.formats.map((f) => ({ type: f.type, owned: f.owned })),
    pricePaid: out.price_paid,
    purchasedAt: out.purchased_at,
    tbrRank: out.tbr_rank,
    tbrNote: out.tbr_note,
    createdAt: out.created_at,
    updatedAt: out.updated_at,
  }
}

function mapSession(s: ReadingSessionWire): ReadingSession {
  return {
    id: s.id,
    bookId: s.book_id,
    startedAt: s.started_at,
    endedAt: s.ended_at,
    durationSec: s.duration_sec,
    startPage: s.start_page,
    endPage: s.end_page,
    pagesRead: s.pages_read,
    note: s.note,
    source: s.source as ReadingSession["source"],
  }
}

function mapHighlight(h: HighlightWire): Highlight {
  return {
    id: h.id,
    bookId: h.book_id,
    bookTitle: h.book_title,
    text: h.text,
    note: h.note,
    page: h.page,
    chapter: h.chapter,
    source: h.source as Highlight["source"],
    highlightedAt: h.highlighted_at,
    createdAt: h.created_at,
  }
}

// ---------------------------------------------------------------------------
// Endpoints
// ---------------------------------------------------------------------------

/** GET /books — liste filtrée/triée/paginée. */
export async function listBooks(query: BooksQuery = {}): Promise<BookList> {
  const data = await request<{ items: BookOutWire[]; total: number; page: number; page_size: number }>(
    `/books${queryString(query as Record<string, string | number | undefined>)}`,
  )
  return { items: data.items.map(mapBook), total: data.total, page: data.page, page_size: data.page_size }
}

/** GET /books/{id} */
export async function getBook(id: number): Promise<Book> {
  const data = await request<BookOutWire>(`/books/${id}`)
  return mapBook(data)
}

/** PATCH /books/{id} — mise à jour partielle. */
export async function updateBook(id: number, payload: BookUpdatePayload): Promise<Book> {
  const data = await request<BookOutWire>(`/books/${id}`, { method: "PATCH", body: payload })
  return mapBook(data)
}

/** POST /books/{id}/status — déplacement rapide de statut. */
export async function setBookStatus(
  id: number,
  body: { status: BookStatus; finished_at?: string },
): Promise<Book> {
  const data = await request<BookOutWire>(`/books/${id}/status`, { method: "POST", body })
  return mapBook(data)
}

/** POST /books/tbr/reorder — l'ordre COMPLET de la PAL (1 = prochain lu). */
export async function reorderTbr(bookIds: number[]): Promise<BookList> {
  const data = await request<{ items: BookOutWire[]; total: number; page: number; page_size: number }>(
    `/books/tbr/reorder`,
    { method: "POST", body: { book_ids: bookIds } },
  )
  return { items: data.items.map(mapBook), total: data.total, page: data.page, page_size: data.page_size }
}

/** GET /books/{id}/sessions — de la plus récente à la plus ancienne. */
export async function listSessions(bookId: number): Promise<SessionList> {
  const data = await request<{ items: ReadingSessionWire[]; total: number }>(
    `/books/${bookId}/sessions`,
  )
  return { items: data.items.map(mapSession), total: data.total }
}

/** GET /books/{id}/highlights */
export async function listHighlights(bookId: number): Promise<HighlightList> {
  const data = await request<{ items: HighlightWire[]; total: number }>(
    `/books/${bookId}/highlights`,
  )
  return { items: data.items.map(mapHighlight), total: data.total }
}

/** POST /timer/start — ouvre une session chrono (transition tbr→reading auto). */
export async function startTimer(bookId: number): Promise<ReadingSession> {
  const data = await request<ReadingSessionWire>(`/timer/start`, {
    method: "POST",
    body: { book_id: bookId },
  })
  return mapSession(data)
}

/** POST /timer/stop — clôture la session chrono ouverte du livre. */
export async function stopTimer(bookId: number, endPage: number): Promise<ReadingSession> {
  const data = await request<ReadingSessionWire>(`/timer/stop`, {
    method: "POST",
    body: { book_id: bookId, end_page: endPage },
  })
  return mapSession(data)
}

/** GET /authors — taxonomie pour les filtres. */
export async function listAuthors(): Promise<Author[]> {
  const data = await request<{ id: number; name: string; openlibrary_key: string | null; book_count: number }[]>(
    `/authors`,
  )
  return data.map((a) => ({
    id: a.id,
    name: a.name,
    openlibraryKey: a.openlibrary_key,
    bookCount: a.book_count,
  }))
}

/** GET /labels?kind=genre|tag */
export async function listLabels(
  kind: "genre" | "tag",
): Promise<{ items: Label[]; total: number }> {
  return request(`/labels?kind=${kind}`)
}

/** GET /series */
export async function listSeries(): Promise<Series[]> {
  const data = await request<{ id: number; name: string; book_count: number }[]>(`/series`)
  return data.map((s) => ({ id: s.id, name: s.name, bookCount: s.book_count }))
}

/** GET /series/{id}/books — tomes de la série, triés par numéro. */
export async function listSeriesBooks(seriesId: number): Promise<SeriesBooks> {
  const data = await request<{
    series: { id: number; name: string; book_count: number }
    books: BookOutWire[]
  }>(`/series/${seriesId}/books`)
  return {
    series: { id: data.series.id, name: data.series.name, bookCount: data.series.book_count },
    books: data.books.map(mapBook),
  }
}
