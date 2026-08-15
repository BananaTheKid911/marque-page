import type { BookStatus, NavItem } from "@/types/book"

/**
 * Constantes de l'application — hors données (issues de l'ex-mock-data.ts,
 * qui a été supprimé : ce sont des constantes, pas des mocks).
 */

export const NAV_ITEMS: NavItem[] = [
  { key: "library", label: "Bibliothèque", href: "/" },
  { key: "tbr", label: "Pile à lire", href: "/pile-a-lire" },
  { key: "add", label: "Ajouter", href: "/ajouter" },
  { key: "stats", label: "Stats", href: "/stats" },
  { key: "settings", label: "Réglages", href: "/reglages" },
]

export const STATUS_LABELS: Record<BookStatus, string> = {
  wishlist: "Wishlist",
  tbr: "À lire",
  reading: "En cours",
  read: "Lu",
  dnf: "Abandonné",
  on_hold: "En pause",
}
