import { motion, useReducedMotion } from "framer-motion";
import { Aperture, Volume2, VolumeX } from "lucide-react";
import { useState, type ReactNode } from "react";
import { msg, useT } from "@/lib/i18n";
import { href, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { LANGUAGES, usePrefs } from "@/state/prefs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";
import { useMatch } from "@/state/match";

const LINKS: { route: Route; label: string }[] = [
  { route: "home", label: msg("Home") },
  { route: "how", label: msg("How it works") },
  { route: "live", label: msg("Live") },
  { route: "recap", label: msg("Recap") },
];

/** Page links with one white underline that glides to the hovered link and back to the current page. */
export function NavLinks({ route }: { route: Route }) {
  const t = useT();
  const reduce = useReducedMotion();
  const [hover, setHover] = useState<Route | null>(null);
  const mark = hover ?? route;
  return (
    <nav aria-label={t("Pages")} className="flex items-center gap-1" onMouseLeave={() => setHover(null)}>
      {LINKS.map((l) => (
        <a
          key={l.route}
          href={href(l.route)}
          aria-current={route === l.route ? "page" : undefined}
          onMouseEnter={() => setHover(l.route)}
          onFocus={() => setHover(l.route)}
          onBlur={() => setHover(null)}
          className={cn(
            "relative px-3 py-2 text-sm font-medium outline-none transition-colors",
            l.route === mark || l.route === route ? "text-ink" : "text-muted hover:text-ink",
          )}
        >
          {t(l.label)}
          {l.route === mark ? (
            <motion.span
              layoutId="nav-underline"
              aria-hidden
              className="absolute inset-x-3 -bottom-0.5 h-0.5 rounded-full bg-white"
              transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 520, damping: 40 }}
            />
          ) : null}
        </a>
      ))}
    </nav>
  );
}

export function Brand() {
  const connected = useMatch((s) => s.connected);
  const t = useT();
  return (
    <a href={href("home")} className="flex items-center gap-2.5">
      <span className="relative grid size-9 place-items-center rounded-lg bg-white text-chrome">
        <Aperture className="size-5" aria-hidden />
        <span
          className={`absolute -right-0.5 -top-0.5 size-2.5 rounded-full ring-2 ring-chrome ${connected ? "bg-green" : "bg-red"}`}
          aria-label={connected ? t("Connected") : t("Disconnected")}
        />
      </span>
      <span className="font-display text-xl font-extrabold tracking-tight">Decision Lens</span>
    </a>
  );
}

/** Mute or unmute the quiet UI sounds (saved per browser). */
export function SoundToggle() {
  const on = usePrefs((s) => s.sound);
  const set = usePrefs((s) => s.set);
  const t = useT();
  return (
    <button
      type="button"
      onClick={() => set({ sound: !on })}
      aria-pressed={on}
      aria-label={on ? t("Mute sounds") : t("Turn sounds on")}
      title={on ? t("Mute sounds") : t("Turn sounds on")}
      className="grid size-10 place-items-center rounded-lg border border-line bg-panel-2 text-muted transition-colors hover:text-ink"
    >
      {on ? <Volume2 className="size-4" aria-hidden /> : <VolumeX className="size-4" aria-hidden />}
    </button>
  );
}

export function PersonaToggle() {
  const persona = usePrefs((s) => s.persona);
  const set = usePrefs((s) => s.set);
  const t = useT();
  return (
    <ToggleGroup
      type="single"
      value={persona}
      onValueChange={(v) => v && set({ persona: v as "analyst" | "fan" })}
      aria-label={t("Persona")}
    >
      <ToggleGroupItem value="analyst">{t("Analyst")}</ToggleGroupItem>
      <ToggleGroupItem value="fan">{t("Fan")}</ToggleGroupItem>
    </ToggleGroup>
  );
}

export function LanguageSelect() {
  const language = usePrefs((s) => s.language);
  const set = usePrefs((s) => s.set);
  const t = useT();
  return (
    <Select value={language} onValueChange={(v) => set({ language: v })}>
      <SelectTrigger className="h-10 w-[124px]" aria-label={t("Language")}>
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
  );
}

/** The purple bar on every page: brand and tabs on the left, page extras in the middle,
 * persona and language on the right. */
export function HeaderShell({ route, children, end }: { route: Route; children?: ReactNode; end?: ReactNode }) {
  return (
    <header className="chrome sticky top-0 z-30 border-b border-line bg-chrome">
      <div className="mx-auto flex min-h-[68px] max-w-[1600px] flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 lg:px-8">
        <Brand />
        <NavLinks route={route} />
        {children}
        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          {end}
          <SoundToggle />
          <PersonaToggle />
          <LanguageSelect />
        </div>
      </div>
    </header>
  );
}

export function PageHeader({ route }: { route: Route }) {
  return <HeaderShell route={route} />;
}
