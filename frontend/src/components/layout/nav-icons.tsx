import {
  BarChart3,
  BookMarked,
  Library,
  Plus,
  Settings2,
  type LucideIcon,
} from "lucide-react"
import type { NavItem } from "@/types/book"

export const NAV_ICONS: Record<NavItem["key"], LucideIcon> = {
  library: Library,
  tbr: BookMarked,
  add: Plus,
  stats: BarChart3,
  settings: Settings2,
}
