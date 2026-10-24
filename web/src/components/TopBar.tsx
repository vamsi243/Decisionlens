import { BarChart3, Pause, Play, Settings2 } from "lucide-react";
import type { Speed } from "@/types/contracts";
import { api } from "@/lib/api";
import { clock } from "@/lib/format";
import { useMatch } from "@/state/match";
import { LANGUAGES, usePrefs } from "@/state/prefs";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";
import { Tooltip } from "./ui/tooltip";

const SPEEDS: Speed[] = [1, 2, 4, 8];

export function TopBar({ onStats, onSettings }: { onStats: () => void; onSettings: () => void }) {
  const meta = useMatch((s) => s.meta);
  const stats = useMatch((s) => s.stats);
  const status = useMatch((s) => s.status);
  const clockMs = useMatch((s) => s.clockMs);
  const connected = useMatch((s) => s.connected);
  const persona = usePrefs((s) => s.persona);
  const language = usePrefs((s) => s.language);
  const setPrefs = usePrefs((s) => s.set);

  const [home, away] = meta?.teams ?? [];
  const goals = (id?: string) => stats?.teams.find((t) => t.team_id === id)?.goals ?? 0;
  const half = clockMs >= (meta?.period_length_ms ?? 2_700_000) ? "2H" : "1H";
  const playing = status?.playing ?? false;

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1500px] flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 lg:px-6">
        <div className="flex items-center gap-2">
          <span
            className={`size-2 rounded-full ${connected ? "bg-green" : "bg-red"}`}
            aria-label={connected ? "Connected" : "Disconnected"}
          />
          <span className="font-display text-base font-semibold tracking-tight">Decision Lens</span>
        </div>

        <div className="flex items-center gap-3 rounded-md border border-line bg-surface px-3 py-1.5 shadow-sm">
          <span className="text-sm font-medium">
            <span className="sm:hidden">{home?.short_name ?? "HOM"}</span>
            <span className="hidden sm:inline">{home?.name ?? "Home"}</span>
          </span>
          <span className="whitespace-nowrap font-display text-lg font-semibold tabular-nums">
            {goals(home?.team_id)} – {goals(away?.team_id)}
          </span>
          <span className="text-sm font-medium">
            <span className="sm:hidden">{away?.short_name ?? "AWY"}</span>
            <span className="hidden sm:inline">{away?.name ?? "Away"}</span>
          </span>
          <span className="h-4 w-px bg-line" />
          <span className="num text-sm text-amber">{clock(clockMs)}</span>
          <span className="num text-xs text-muted-2">{half}</span>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button
            variant="primary"
            size="icon"
            aria-label={playing ? "Pause" : "Play"}
            onClick={() => (playing ? api.pause() : api.play())}
          >
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          </Button>
          <ToggleGroup
            type="single"
            value={String(status?.speed ?? 1)}
            onValueChange={(v) => v && api.speed(Number(v) as Speed)}
            aria-label="Replay speed"
          >
            {SPEEDS.map((s) => (
              <ToggleGroupItem key={s} value={String(s)} className="num">
                {s}×
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <ToggleGroup
            type="single"
            value={persona}
            onValueChange={(v) => v && setPrefs({ persona: v as "analyst" | "fan" })}
            aria-label="Persona"
          >
            <ToggleGroupItem value="analyst">Analyst</ToggleGroupItem>
            <ToggleGroupItem value="fan">Fan</ToggleGroupItem>
          </ToggleGroup>
          <Select value={language} onValueChange={(v) => setPrefs({ language: v })}>
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
          <Tooltip label="Stats">
            <Button size="icon" aria-label="Open stats" onClick={onStats}>
              <BarChart3 className="size-4" />
            </Button>
          </Tooltip>
          <Tooltip label="Settings">
            <Button size="icon" aria-label="Open settings" onClick={onSettings}>
              <Settings2 className="size-4" />
            </Button>
          </Tooltip>
        </div>
      </div>
    </header>
  );
}
