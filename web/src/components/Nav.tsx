import { Aperture } from "lucide-react";
import type { ReactNode } from "react";
import { href, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { LANGUAGES, usePrefs } from "@/state/prefs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";
import { useMatch } from "@/state/match";

const LINKS: { route: Route; label: string }[] = [
  { route: "home", label: "Home" },
  { route: "how", label: "How it works" },
  { route: "live", label: "Live" },
  { route: "recap", label: "Recap" },
];

export function NavLinks({ route }: { route: Route }) {
  return (
    <nav aria-label="Pages" className="flex items-center gap-1 rounded-lg border border-line bg-panel-2 p-1">
      {LINKS.map((l) => (
        <a
          key={l.route}
          href={href(l.route)}
          aria-current={route === l.route ? "page" : undefined}
          className={cn(
            "rounded-md px-3 py-1.5 text-sm font-medium text-muted transition-colors hover:text-ink",
            route === l.route && "bg-surface text-ink shadow-sm",
          )}
        >
          {l.label}
        </a>
      ))}
    </nav>
  );
}

export function Brand() {
  const connected = useMatch((s) => s.connected);
  return (
    <a href={href("home")} className="flex items-center gap-2.5">
      <span className="relative grid size-9 place-items-center rounded-lg bg-white text-chrome">
        <Aperture className="size-5" aria-hidden />
        <span
          className={`absolute -right-0.5 -top-0.5 size-2.5 rounded-full ring-2 ring-chrome ${connected ? "bg-green" : "bg-red"}`}
          aria-label={connected ? "Connected" : "Disconnected"}
        />
      </span>
      <span className="font-display text-xl font-semibold tracking-tight">Decision Lens</span>
    </a>
  );
}

export function PersonaToggle() {
  const persona = usePrefs((s) => s.persona);
  const set = usePrefs((s) => s.set);
  return (
    <ToggleGroup
      type="single"
      value={persona}
      onValueChange={(v) => v && set({ persona: v as "analyst" | "fan" })}
      aria-label="Persona"
    >
      <ToggleGroupItem value="analyst">Analyst</ToggleGroupItem>
      <ToggleGroupItem value="fan">Fan</ToggleGroupItem>
    </ToggleGroup>
  );
}

export function LanguageSelect() {
  const language = usePrefs((s) => s.language);
  const set = usePrefs((s) => s.set);
  return (
    <Select value={language} onValueChange={(v) => set({ language: v })}>
      <SelectTrigger className="h-10 w-[124px]" aria-label="Language">
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

/** The black bar on every page: brand and tabs on the left, page extras in the middle,
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
