import { Radio } from "lucide-react";
import { stopClip } from "@/lib/clip";
import { clock } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useMatch } from "@/state/match";
import { HeaderShell } from "./Nav";
import { Button } from "./ui/button";

/** The purple bar across the top of the live page: pages, persona, sound and language. */
export function TopBar() {
  return <HeaderShell route="live" />;
}

/** The score card above the pitch: teams, score, clock and half, and the live state. */
export function ScoreStrip() {
  const meta = useMatch((s) => s.meta);
  const stats = useMatch((s) => s.stats);
  const clockMs = useMatch((s) => s.clockMs);
  const live = useMatch((s) => s.server?.live ?? false);
  const clip = useMatch((s) => s.clip);
  const t = useT();

  const [home, away] = meta?.teams ?? [];
  const goals = (id?: string) => stats?.teams.find((t) => t.team_id === id)?.goals ?? 0;
  const half = clockMs >= (meta?.period_length_ms ?? 2_700_000) ? "2H" : "1H";

  return (
    <div className="mb-5 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-line bg-surface px-4 py-2.5">
      <span className="inline-flex items-center gap-2.5">
        <span className="size-3 rounded-[3px] bg-riv" aria-hidden />
        <span className="font-display text-lg font-extrabold tracking-tight">
          <span className="sm:hidden">{home?.short_name ?? "HOM"}</span>
          <span className="hidden sm:inline">{home?.name ?? "Home"}</span>
        </span>
      </span>
      <span className="whitespace-nowrap rounded-lg bg-chrome px-3 py-0.5 font-display text-2xl font-black tabular-nums text-white">
        {goals(home?.team_id)} – {goals(away?.team_id)}
      </span>
      <span className="inline-flex items-center gap-2.5">
        <span className="font-display text-lg font-extrabold tracking-tight">
          <span className="sm:hidden">{away?.short_name ?? "AWY"}</span>
          <span className="hidden sm:inline">{away?.name ?? "Away"}</span>
        </span>
        <span className="size-3 rounded-[3px] bg-hil" aria-hidden />
      </span>
      <span className="ml-auto inline-flex items-center gap-3">
        <span className="num text-sm text-muted">
          {clock(clockMs)} <span className="text-muted-2">{half}</span>
        </span>
        {live ? (
          clip ? (
            <Button variant="primary" size="sm" onClick={stopClip}>
              <Radio className="size-3.5" aria-hidden /> {t("Back to live")}
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-live px-2.5 py-1 text-xs font-semibold tracking-wide text-white">
              <span className="size-1.5 animate-pulse rounded-full bg-white" aria-hidden /> {t("LIVE")}
            </span>
          )
        ) : null}
      </span>
    </div>
  );
}
