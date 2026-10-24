import type { ReactNode } from "react";
import { msg, useT } from "@/lib/i18n";
import { useMatch } from "@/state/match";
import { LANGUAGES, usePrefs, type WhatIfProfile } from "@/state/prefs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Sheet, SheetContent } from "./ui/sheet";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

const ANY = "__any";

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  const t = useT();
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">{t(label)}</span>
      {children}
      {hint ? <span className="text-xs text-muted">{t(hint)}</span> : null}
    </div>
  );
}

export function SettingsSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const prefs = usePrefs();
  const meta = useMatch((s) => s.meta);
  const players = useMatch((s) => s.players);
  const t = useT();
  const squad = Object.values(players)
    .filter((p) => !prefs.club || p.team_id === prefs.club)
    .sort((a, b) => a.team_id.localeCompare(b.team_id) || a.shirt_number - b.shirt_number);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title={t("Your view")} description={t("Saved on this device.")}>
        <div className="flex flex-col gap-5">
          <Field label={msg("Persona")} hint={msg("Analysts get ranges, drivers and option maps; fans get the follow-cam, commentary and plain words.")}>
            <ToggleGroup type="single" value={prefs.persona} onValueChange={(v) => v && prefs.set({ persona: v as "analyst" | "fan" })}>
              <ToggleGroupItem value="analyst">{t("Analyst")}</ToggleGroupItem>
              <ToggleGroupItem value="fan">{t("Fan")}</ToggleGroupItem>
            </ToggleGroup>
          </Field>
          <Field label={msg("Favourite club")}>
            <Select value={prefs.club ?? ANY} onValueChange={(v) => prefs.set({ club: v === ANY ? null : v, player: null })}>
              <SelectTrigger aria-label={t("Favourite club")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("No favourite")}</SelectItem>
                {meta?.teams.map((t) => (
                  <SelectItem key={t.team_id} value={t.team_id}>
                    {t.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={msg("Favourite player")} hint={msg("Highlighted on the board with a halo and name tag.")}>
            <Select value={prefs.player ?? ANY} onValueChange={(v) => prefs.set({ player: v === ANY ? null : v })}>
              <SelectTrigger aria-label={t("Favourite player")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ANY}>{t("No favourite")}</SelectItem>
                {squad.map((p) => (
                  <SelectItem key={p.player_id} value={p.player_id}>
                    {p.shirt_number} · {p.name} ({p.team_id})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={msg("Language")} hint={msg("Everything on screen switches language: fixed wording from the app, match text through Azure AI Translator (no new model call), and the copilot answers in it. Without a Translator key match text stays in English.")}>
            <Select value={prefs.language} onValueChange={(v) => prefs.set({ language: v })}>
              <SelectTrigger aria-label={t("Language")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LANGUAGES.map((l) => (
                  <SelectItem key={l.code} value={l.code}>
                    {l.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </Field>
          <Field label={msg("What-if profile")} hint={msg("Who the engine swaps in at a key moment.")}>
            <Select value={prefs.whatIf} onValueChange={(v) => prefs.set({ whatIf: v as WhatIfProfile })}>
              <SelectTrigger aria-label={t("What-if profile")}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto">{t("Best fit (fresh sub if available)")}</SelectItem>
                <SelectItem value="fresh_sub">{t("Fresh substitute")}</SelectItem>
                <SelectItem value="archetype">{t("Textbook archetype")}</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label={msg("Pause at key moments")} hint={msg("Stops the replay so you can read the option map.")}>
            <ToggleGroup
              type="single"
              value={prefs.pauseAtMoments ? "on" : "off"}
              onValueChange={(v) => v && prefs.set({ pauseAtMoments: v === "on" })}
            >
              <ToggleGroupItem value="on">{t("On")}</ToggleGroupItem>
              <ToggleGroupItem value="off">{t("Off")}</ToggleGroupItem>
            </ToggleGroup>
          </Field>
        </div>
      </SheetContent>
    </Sheet>
  );
}
