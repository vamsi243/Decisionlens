import { BarChart3, Pause, Play, Settings2 } from "lucide-react";
import type { Speed } from "@/types/contracts";
import { api } from "@/lib/api";
import { surname } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { useUi } from "@/state/ui";
import { Button } from "../ui/button";
import { ToggleGroup, ToggleGroupItem } from "../ui/toggle-group";
import { Tooltip } from "../ui/tooltip";
import { Scrubber } from "../Scrubber";
import { Board } from "./Board";

const SPEEDS: Speed[] = [1, 2, 4, 8];

/** Replay controls down the side of the table (a row under it on narrow screens). */
function ControlRail({ onStats, onSettings }: { onStats: () => void; onSettings: () => void }) {
  const status = useMatch((s) => s.status);
  const live = useMatch((s) => s.server?.live ?? false);
  const playing = status?.playing ?? false;
  return (
    <div className="chrome flex items-center gap-2 rounded-lg bg-panel-2 p-1.5 lg:flex-col">
      {/* A shared live broadcast can't be paused or sped up. */}
      {live ? null : (
        <>
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
            orientation="vertical"
            value={String(status?.speed ?? 1)}
            onValueChange={(v) => v && api.speed(Number(v) as Speed)}
            aria-label="Replay speed"
            className="border-0 lg:flex-col"
          >
            {SPEEDS.map((s) => (
              <ToggleGroupItem key={s} value={String(s)} className="num w-9">
                {s}×
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </>
      )}
      <div className="ml-auto flex items-center gap-2 lg:ml-0 lg:mt-auto lg:flex-col">
        <Tooltip label="Stats">
          <Button size="icon" variant="ghost" aria-label="Open stats" onClick={onStats}>
            <BarChart3 className="size-4" />
          </Button>
        </Tooltip>
        <Tooltip label="Settings">
          <Button size="icon" variant="ghost" aria-label="Open settings" onClick={onSettings}>
            <Settings2 className="size-4" />
          </Button>
        </Tooltip>
      </div>
    </div>
  );
}

/** Each team's players who aren't on the pitch right now (subs, and anyone subbed off). */
function BenchStrip() {
  const meta = useMatch((s) => s.meta);
  const players = useMatch((s) => s.players);
  const onPitch = useMatch((s) => s.onPitch);
  const focus = usePrefs((s) => s.player);
  if (!meta || onPitch.length === 0) return null;
  const on = new Set(onPitch);
  return (
    <div className="chrome grid gap-x-6 gap-y-1.5 px-1 sm:grid-cols-2">
      {meta.teams.map((team, i) => {
        const bench = Object.values(players)
          .filter((p) => p.team_id === team.team_id && !on.has(p.player_id))
          .sort((a, b) => a.shirt_number - b.shirt_number);
        return (
          <div key={team.team_id} className={cn("flex flex-wrap items-center gap-1.5", i === 1 && "sm:justify-end")}>
            <span className={cn("text-[11px] font-medium uppercase tracking-wide", i === 0 ? "text-white" : "text-hil")}>
              {team.short_name} bench
            </span>
            {bench.map((p) => (
              <button
                key={p.player_id}
                type="button"
                aria-pressed={focus === p.player_id}
                onClick={() => useUi.getState().openPanel(p.player_id)}
                className={cn(
                  "inline-flex items-center gap-1 rounded-full border border-line px-2 py-0.5 text-xs text-muted transition-colors hover:text-ink",
                  focus === p.player_id && "border-line-2 text-ink",
                )}
              >
                <span
                  className={cn(
                    "num grid size-4 place-items-center rounded-full text-[9px] font-semibold",
                    i === 0 ? "bg-riv text-white" : "bg-hil text-hil-ink",
                  )}
                >
                  {p.shirt_number}
                </span>
                {surname(p.name)}
              </button>
            ))}
          </div>
        );
      })}
    </div>
  );
}

/** The tactics table: the pitch in a black frame, controls down the side, then the timeline and
 * the benches underneath. */
export function Table({ onStats, onSettings }: { onStats: () => void; onSettings: () => void }) {
  return (
    <div className="flex flex-col gap-2.5 rounded-2xl bg-chrome p-2.5 shadow-lg">
      <div className="flex flex-col gap-2.5 lg:flex-row">
        <div className="min-w-0 flex-1">
          <Board />
        </div>
        <ControlRail onStats={onStats} onSettings={onSettings} />
      </div>
      <Scrubber />
      <BenchStrip />
    </div>
  );
}
