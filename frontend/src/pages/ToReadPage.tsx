import { useEffect, useState } from "react"
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { ApiError, listBooks, reorderTbr } from "@/lib/api"
import { useBooks } from "@/context/books"
import { useAsyncData } from "@/lib/hooks"
import { CurrentlyReadingCard } from "@/components/reading/CurrentlyReadingCard"
import { ToReadRow } from "@/components/tbr/ToReadRow"
import type { Book } from "@/types/book"

/**
 * Pile à lire = "la sélection" : une liste curatée à la main, ordonnée
 * (GET /books?status=tbr&sort=tbr_rank), distincte du simple filtre
 * `status==="tbr"` de la Bibliothèque. Le réordonnancement POST l'ordre
 * COMPLET via /books/tbr/reorder — strict : en cas de 422 (liste périmée),
 * on recharge la liste côté front, jamais de correction partielle. La
 * réponse du POST remplace l'état local sans round-trip.
 *
 * Drag via dnd-kit (PointerSensor, distance 8 px) : la poignée seule
 * déclenche le drag (ToReadRow), le reste de la ligne navigue vers le
 * Détail. Fonctionne en tactile (la MagicPad est une cible).
 */
export function ToReadPage() {
  const { currentlyReading, booksVersion, notifyBooksChanged } = useBooks()

  const { data, error, loading, reload } = useAsyncData(
    () => listBooks({ status: "tbr", sort: "tbr_rank", page_size: 100 }),
    [booksVersion],
  )

  // Ordre local : initialisé depuis le serveur, remplacé par la réponse du
  // POST reorder (sans round-trip) ou par un rechargement après 422.
  const [items, setItems] = useState<Book[]>([])
  useEffect(() => {
    if (data) setItems(data.items)
  }, [data])

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
  )

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const from = items.findIndex((b) => String(b.id) === active.id)
    const to = items.findIndex((b) => String(b.id) === over.id)
    if (from < 0 || to < 0) return

    // Optimiste : on applique l'ordre avant même la réponse serveur.
    const next = arrayMove(items, from, to)
    setItems(next)
    setSaveError(null)
    void persistOrder(next)
  }

  async function persistOrder(order: Book[]) {
    setSaving(true)
    try {
      const result = await reorderTbr(order.map((b) => b.id))
      // Le serveur renvoie la PAL dans son nouvel ordre : remplacement direct.
      setItems(result.items)
      notifyBooksChanged()
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setSaveError("La pile à lire a changé ailleurs — liste rechargée.")
      } else {
        setSaveError(
          err instanceof Error ? err.message : "Réordonnancement impossible — liste rechargée.",
        )
      }
      // Tout échec = recharger : l'état serveur fait foi, pas notre optimisme.
      reload()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="@min-[700px]:hidden">
        <CurrentlyReadingCard data={currentlyReading} variant="banner" />
      </div>

      <div className="flex items-baseline justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-ink-mute">
            La sélection
          </p>
          <h1 className="text-[19px] font-semibold text-ink @min-[1200px]:text-[22px]">
            Pile à lire
          </h1>
        </div>
        {!loading && (
          <span className="text-[12.5px] tabular-nums text-ink-mute">
            {items.length} livre{items.length > 1 ? "s" : ""}
          </span>
        )}
      </div>

      {error ? (
        <div className="flex flex-col items-start gap-3 rounded-[4px] border border-line bg-card p-4">
          <p className="text-[13.5px] text-ink-soft">
            Chargement impossible : {error instanceof Error ? error.message : String(error)}
          </p>
          <button
            type="button"
            onClick={reload}
            className="rounded-[3px] border border-ink px-3 py-1.5 text-[13px] text-ink transition-colors hover:bg-card"
          >
            Réessayer
          </button>
        </div>
      ) : items.length === 0 ? (
        <p className="py-16 text-center text-[15px] text-ink-mute">
          Rien en attente — la bibliothèque est à jour.
        </p>
      ) : (
        <>
          {saveError && (
            <p className="rounded-[4px] border border-line bg-card px-4 py-3 text-[13px] text-ink-soft">
              {saveError}
            </p>
          )}
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext
              items={items.map((b) => String(b.id))}
              strategy={verticalListSortingStrategy}
            >
              <ul className="flex flex-col divide-y divide-line-2">
                {items.map((book, i) => (
                  <SortableToReadRow key={book.id} book={book} position={i + 1} />
                ))}
              </ul>
            </SortableContext>
          </DndContext>
          {saving && (
            <p className="text-[12.5px] text-ink-mute" aria-live="polite">
              Enregistrement de l'ordre…
            </p>
          )}
        </>
      )}
    </div>
  )
}

/** Ligne rendue draggable par dnd-kit ; les handlers vont à la poignée. */
function SortableToReadRow({ book, position }: { book: Book; position: number }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: String(book.id),
  })

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
    >
      <ToReadRow
        book={book}
        position={position}
        isDragging={isDragging}
        dragHandleProps={{ ...attributes, ...listeners }}
      />
    </li>
  )
}
