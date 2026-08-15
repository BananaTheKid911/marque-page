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

/**
 * Réglages. Écran "sans couverture" (AGENTS.md) — pas d'image, pas
 * d'accent. Tout mock/no-op : formulaires inertes, aucun submit réel
 * (frontend-dev branche APP_PASSWORD, SESSION_GAP_SEC, /export, /koreader
 * /import). Aucun bouton n'est rempli d'encre ici : contrairement à la
 * page Détail, aucune action ne domine vraiment les autres sur cet écran,
 * donc la masse noire (réservée à UN point de fixation par écran) n'est
 * pas utilisée — tout reste en outline.
 */
export function SettingsPage() {
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
          <Button variant="outline" size="default" className="rounded-[3px]">
            Choisir un fichier
          </Button>
        </SettingsRow>
        <SettingsRow
          label="Dernier import"
          hint={`${formatDateLong("2026-08-12T19:20:00")} — 2 livres non rattachés à confirmer`}
        >
          <a
            href="/reglages/koreader-non-rattaches"
            className="text-[13px] font-medium text-ink underline underline-offset-2"
          >
            Rattacher
          </a>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Sauvegarde">
        <SettingsRow
          label="Exporter mes données"
          hint="Dump JSON complet — base et couvertures ne sont pas dans le backup 3-2-1"
        >
          <Button variant="outline" size="default" className="rounded-[3px]">
            Exporter (JSON)
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
