import { Radio } from "lucide-react";
import { stopClip } from "@/lib/clip";
import { clock } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { useMatch } from "@/state/match";
import { HeaderShell } from "./Nav";
import { Button } from "./ui/button";

/** The black bar across the top: pages, score and clock, live state, persona and language. */
export function TopBar() {
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
    <HeaderShell
      route="live"
      end={
        live ? (
          clip ? (
            <Button variant="primary" size="sm" onClick={stopClip}>
              <Radio className="size-3.5" aria-hidden /> {t("Back to live")}
            </Button>
          ) : (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-[#3a1212] px-2.5 py-1 text-xs font-semibold tracking-wide text-[#ff6b62]">
              <span className="size-1.5 animate-pulse rounded-full bg-[#ff6b62]" aria-hidden /> {t("LIVE")}
            </span>
          )
        ) : null
      }
    >
      <div className="flex items-center gap-3 rounded-lg bg-panel-2 px-4 py-2">
        <span className="inline-flex items-center gap-2 text-sm font-medium">
          <span className="size-2.5 rounded-full bg-riv" aria-hidden />
          <span className="sm:hidden">{home?.short_name ?? "HOM"}</span>
          <span className="hidden sm:inline">{home?.name ?? "Home"}</span>
        </span>
        <span className="whitespace-nowrap font-display text-xl font-semibold tabular-nums">
          {goals(home?.team_id)} – {goals(away?.team_id)}
        </span>
        <span className="inline-flex items-center gap-2 text-sm font-medium">
          <span className="sm:hidden">{away?.short_name ?? "AWY"}</span>
          <span className="hidden sm:inline">{away?.name ?? "Away"}</span>
          <span className="size-2.5 rounded-full bg-hil" aria-hidden />
        </span>
        <span className="h-4 w-px bg-line-2" />
        <span className="num text-sm text-[#ffb547]">{clock(clockMs)}</span>
        <span className="num text-xs text-muted-2">{half}</span>
      </div>
    </HeaderShell>
  );
}
