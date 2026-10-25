import { BarChart3, Pause, Play, Settings2 } from "lucide-react";
import type { Speed } from "@/types/contracts";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { surname } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { useFocus, usePrefs } from "@/state/prefs";
import { useUi } from "@/state/ui";
import { Button } from "../ui/button";
import { ToggleGroup, ToggleGroupItem } from "../ui/toggle-group";
import { Tooltip } from "../ui/tooltip";
import { CommentaryTicker, MomentumBar } from "../fan/FanOverlays";
import { Scrubber } from "../Scrubber";
import { Board } from "./Board";

const SPEEDS: Speed[] = [1, 2, 4, 8];

/** Play/pause and the replay speeds, at the start of the control bar under the pitch. */
function PlayControls() {
  const status = useMatch((s) => s.status);
  const live = useMatch((s) => s.server?.live ?? false);
  const playing = status?.playing ?? false;
  // Fans get play/pause; speeds are an analyst tool.
  const fan = usePrefs((s) => s.persona) === "fan";
  const t = useT();
  // A shared live broadcast can't be paused or sped up.
  if (live) return null;
  return (
    <div className="flex items-center gap-1.5">
      <Button
        variant="primary"
        size="icon"
        aria-label={playing ? t("Pause") : t("Play")}
        onClick={() => {
          sfx.tap();
          void (playing ? api.pause() : api.play());
        }}
      >
        {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
      </Button>
      {fan ? null : (
        <ToggleGroup
          type="single"
          value={String(status?.speed ?? 1)}
          onValueChange={(v) => {
            if (!v) return;
            sfx.tap();
            void api.speed(Number(v) as Speed);
          }}
          aria-label={t("Replay speed")}
          className="border-0 bg-panel-2"
        >
          {SPEEDS.map((s) => (
            <ToggleGroupItem key={s} value={String(s)} className="num w-9">
              {s}×
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      )}
    </div>
  );
}

/** Stats (analysts) and settings, at the end of the control bar. */
function ToolButtons({
  onStats,
  onSettings,
}: {
  onStats: () => void;
  onSettings: () => void;
}) {
  const fan = usePrefs((s) => s.persona) === "fan";
  const t = useT();
  return (
    <div className="ml-auto flex items-center gap-1">
      {fan ? null : (
        <Tooltip label={t("Stats")}>
          <Button
            size="icon"
            variant="ghost"
            aria-label={t("Open stats")}
            onClick={onStats}
          >
            <BarChart3 className="size-4" />
          </Button>
        </Tooltip>
      )}
      <Tooltip label={t("Settings")}>
        <Button
          size="icon"
          variant="ghost"
          aria-label={t("Open settings")}
          onClick={onSettings}
        >
          <Settings2 className="size-4" />
        </Button>
      </Tooltip>
    </div>
  );
}

/** Each team's players who aren't on the pitch right now (subs, and anyone subbed off). */
function BenchStrip() {
  const meta = useMatch((s) => s.meta);
  const players = useMatch((s) => s.players);
  const onPitch = useMatch((s) => s.onPitch);
  const focus = useFocus();
  const t = useT();
  if (!meta || onPitch.length === 0) return null;
  const on = new Set(onPitch);
  return (
    // Sized by the table's own width (a container query), so it reflows as the split is dragged.
    <div className="@container">
      <div className="grid gap-3 @lg:grid-cols-2">
        {meta.teams.map((team, i) => {
          const bench = Object.values(players)
            .filter((p) => p.team_id === team.team_id && !on.has(p.player_id))
            .sort((a, b) => a.shirt_number - b.shirt_number);
          return (
            <section
              key={team.team_id}
              aria-label={t("{team} bench", { team: team.short_name })}
              className="rounded-xl border border-line bg-bg p-3"
            >
              <h3
                className={cn(
                  "mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide",
                  i === 0 ? "text-riv-ink" : "text-hil-ink",
                )}
              >
                <span
                  className={cn(
                    "size-2 rounded-[2px]",
                    i === 0 ? "bg-riv" : "bg-hil",
                  )}
                  aria-hidden
                />
                {t("{team} bench", { team: team.short_name })}
              </h3>
              <div className="flex flex-wrap gap-1.5">
                {bench.map((p) => (
                  <button
                    key={p.player_id}
                    type="button"
                    aria-pressed={focus === p.player_id}
                    onClick={() => useUi.getState().openPanel(p.player_id)}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-xs text-muted transition-colors hover:text-ink",
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
                {bench.length === 0 ? (
                  <span className="text-xs text-muted-2">–</span>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

/** The tactics table: the pitch on a white card, then one control bar (play and speed, the
 * timeline, stats and settings) and the two benches. Fans also get a momentum bar above and live
 * commentary under the pitch. */
export function Table({
  onStats,
  onSettings,
}: {
  onStats: () => void;
  onSettings: () => void;
}) {
  const fan = usePrefs((s) => s.persona) === "fan";
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-3 shadow-sm">
      {fan ? <MomentumBar /> : null}
      <Board />
      {fan ? <CommentaryTicker /> : null}
      <div className="@container flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-line bg-surface p-1.5">
        <PlayControls />
        <Scrubber className="flex-1 @max-xl:order-last @max-xl:basis-full" />
        <ToolButtons onStats={onStats} onSettings={onSettings} />
      </div>
      <BenchStrip />
    </div>
  );
}
