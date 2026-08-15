import type { FormEvent } from "react"
import { Search } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

interface TextSearchFormProps {
  titleValue: string
  onTitleChange: (value: string) => void
  authorValue: string
  onAuthorChange: (value: string) => void
  onSubmit: (e: FormEvent<HTMLFormElement>) => void
  disabled?: boolean
}

/** Recherche par titre/auteur — l'autre voie d'entrée (spec §4), pour les
 * livres sans exemplaire physique sous la main. Seul bouton d'encre du
 * panneau : c'est la seule action possible ici. */
export function TextSearchForm({
  titleValue,
  onTitleChange,
  authorValue,
  onAuthorChange,
  onSubmit,
  disabled,
}: TextSearchFormProps) {
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor="add-search-title" className="text-[12.5px] text-ink-mute">
          Titre
        </label>
        <Input
          id="add-search-title"
          type="text"
          placeholder="La Horde du Contrevent"
          value={titleValue}
          onChange={(e) => onTitleChange(e.target.value)}
          className="h-11 rounded-[3px] text-[15px]"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="add-search-author" className="text-[12.5px] text-ink-mute">
          Auteur <span className="text-ink-mute/70">(optionnel)</span>
        </label>
        <Input
          id="add-search-author"
          type="text"
          placeholder="Alain Damasio"
          value={authorValue}
          onChange={(e) => onAuthorChange(e.target.value)}
          className="h-11 rounded-[3px] text-[15px]"
        />
      </div>

      <Button
        type="submit"
        disabled={disabled || titleValue.trim().length === 0}
        className="mt-1 h-11 self-start rounded-[3px] px-5 text-[15px]"
      >
        <Search className="h-4 w-4" aria-hidden="true" />
        Rechercher
      </Button>
    </form>
  )
}
