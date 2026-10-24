import { href, type Route } from "@/lib/router";
import { cn } from "@/lib/utils";
import { LANGUAGES, usePrefs } from "@/state/prefs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";
import { useMatch } from "@/state/match";

const LINKS: { route: Route; label: string }[] = [
  { route: "live", label: "Live" },
  { route: "recap", label: "Recap" },
  { route: "how", label: "How it works" },
];

export function NavLinks({ route }: { route: Route }) {
  return (
    <nav aria-label="Pages" className="flex items-center gap-0.5 rounded-md border border-line bg-panel-2 p-0.5">
      {LINKS.map((l) => (
        <a
          key={l.route}
          href={href(l.route)}
          aria-current={route === l.route ? "page" : undefined}
          className={cn(
            "rounded-[9px] px-2.5 py-1 text-xs font-medium text-muted transition-colors hover:text-ink",
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
    <a href={href("live")} className="flex items-center gap-2">
      <span
        className={`size-2 rounded-full ${connected ? "bg-green" : "bg-red"}`}
        aria-label={connected ? "Connected" : "Disconnected"}
      />
      <span className="font-display text-base font-semibold tracking-tight">Decision Lens</span>
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
      <SelectTrigger className="h-9 w-[118px]" aria-label="Language">
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

/** Header for the scroll pages (the live page has the full control bar). */
export function PageHeader({ route }: { route: Route }) {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 lg:px-6">
        <Brand />
        <NavLinks route={route} />
        <div className="ml-auto flex items-center gap-2">
          <PersonaToggle />
          <LanguageSelect />
        </div>
      </div>
    </header>
  );
}
