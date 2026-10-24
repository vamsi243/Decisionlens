import { ArrowRight, Footprints, RotateCcw, Star } from "lucide-react";
import { useEffect, useState } from "react";
import type { PlayerDecision, PlayerDecisions, PlayerStats } from "@/types/contracts";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";
import { msg, useT } from "@/lib/i18n";
import { useTr } from "@/lib/tr";
import { activeMoment } from "@/lib/moments";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { useUi } from "@/state/ui";
import { Button } from "./ui/button";
import { Sheet, SheetContent } from "./ui/sheet";

const REFRESH_MS = 20_000;

/** Goal odds as shown everywhere: one decimal under 10%, whole numbers above. */
export function odds(p: number): string {
  const v = p * 100;
  return `${v < 10 ? v.toFixed(1) : Math.round(v)}%`;
}

function useLive<T>(id: string | null, load: (id: string) => Promise<T>): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    setData(null);
    if (!id) return;
    let alive = true;
    const get = () =>
      load(id)
        .then((d) => alive && setData(d))
        .catch(() => undefined);
    void get();
    const t = setInterval(get, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [id, load]);
  return data;
}

function Tile({ label, value, tone }: { label: string; value: string; tone?: "warn" }) {
  const t = useT();
  return (
    <div className="rounded-lg bg-panel-2 px-3 py-2">
      <p className="text-[11px] text-muted">{t(label)}</p>
      <p className={cn("num mt-0.5 text-base font-medium", tone === "warn" && "text-amber")}>{t(value)}</p>
    </div>
  );
}

const loadStats = (id: string) => api.playerStats(id);
const loadDecisions = (id: string) => api.playerDecisions(id);

function StatsGrid({ s }: { s: PlayerStats }) {
  const tiles: [string, string, "warn"?][] = [
    ["Distance", `${s.distance_km.toFixed(1)} km`],
    ["Fatigue", `${Math.round(s.fatigue)} / 100`, s.fatigue >= 70 ? "warn" : undefined],
    ["Sprints", String(s.sprints)],
    ["Top speed", s.top_speed_loss_pct ? `−${s.top_speed_loss_pct}%` : msg("full"), s.top_speed_loss_pct >= 10 ? "warn" : undefined],
    ["Passes", `${s.passes_completed ?? 0} / ${s.passes ?? 0}`],
    ["Shots · goals", `${s.shots ?? 0} · ${s.goals ?? 0}`],
    ["Tackles won", `${s.tackles_won ?? 0} / ${s.tackles ?? 0}`],
    ["Aerials won", `${s.aerial_won ?? 0} / ${s.aerial_duels ?? 0}`],
    ["Interceptions", String(s.interceptions ?? 0)],
  ];
  return (
    <div className="grid grid-cols-3 gap-2">
      {tiles.map(([l, v, t]) => (
        <Tile key={l} label={l} value={v} tone={t} />
      ))}
    </div>
  );
}

export { StatsGrid };

function DecisionRow({ d, fan, live }: { d: PlayerDecision; fan: boolean; live: boolean }) {
  // the minute is already in the row header
  const text = d.text?.[fan ? "fan" : "analyst"]?.en?.replace(/^\d+'\s*/, "");
  const t = useT();
  const tr = useTr();
  const kind = t(d.positive ? msg("Best decision") : d.kind === "defending" ? msg("Defending") : msg("On the ball"));
  const minute = Math.floor(d.t_ms / 60_000) + 1;
  return (
    <li className="rounded-xl border border-line bg-surface p-3.5">
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="num text-amber">{minute}'</span>
        <span className="rounded-full bg-panel-2 px-2 py-0.5 font-medium text-ink">{kind}</span>
        {!live ? (
          <button
            type="button"
            onClick={() => {
              useMatch.getState().pin(null);
              void api.seek(Math.max(0, d.t_ms - 4000)).then(() => api.play());
            }}
            className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-panel-2 hover:text-ink"
            aria-label={t("Replay minute {minute}", { minute })}
          >
            <RotateCcw className="size-3.5" aria-hidden /> Replay
          </button>
        ) : null}
      </div>
      <p
        className={cn(
          "mt-2 flex items-start gap-2 rounded-md px-2 py-1.5 text-sm leading-snug",
          d.positive ? "bg-green/10 text-green" : "bg-red/10 text-red",
        )}
      >
        <span aria-hidden className="mt-[3px] text-[10px] leading-none">
          {d.positive ? "▲" : "▼"}
        </span>
        <span className="sr-only">{d.positive ? "Good decision:" : "Costly decision:"}</span>
        <span>{tr(text)}</span>
      </p>
    </li>
  );
}

/** Click a player: their numbers, the moment they're in, and the decisions that shaped their game.
 * Non-modal, so the board keeps playing and another player can be clicked straight away. */
export function PlayerPanel() {
  const id = useUi((s) => s.panel);
  const openPanel = useUi((s) => s.openPanel);
  const p = useMatch((s) => (id ? s.players[id] : undefined));
  const teams = useMatch((s) => s.meta?.teams);
  const live = useMatch((s) => s.server?.live ?? false);
  const seen = useMatch((s) => s.seen);
  const analyses = useMatch((s) => s.analyses);
  const clockMs = useMatch((s) => s.clockMs);
  const pinned = useMatch((s) => s.pinned);
  const persona = usePrefs((s) => s.persona);
  const followed = usePrefs((s) => s.player);
  const setPrefs = usePrefs((s) => s.set);
  const stats = useLive<PlayerStats>(id, loadStats);
  const decisions = useLive<PlayerDecisions>(id, loadDecisions);
  const fan = persona === "fan";
  const t = useT();
  const tr = useTr();

  const team = teams?.find((t) => t.team_id === p?.team_id);
  const home = team !== undefined && team.team_id === teams?.[0]?.team_id;
  const active = activeMoment(seen, analyses, clockMs, pinned);
  const inMoment = id && active?.moment.players.includes(id) ? active : null;
  const w = inMoment?.what_if?.actor_id === id ? inMoment.what_if : null;

  return (
    <Sheet open={id !== null} modal={false} onOpenChange={(o) => !o && openPanel(null)}>
      <SheetContent
        overlay={false}
        title={p?.name ?? "Player"}
        description={p ? `#${p.shirt_number} · ${p.position} · ${team?.name ?? ""}` : undefined}
        onInteractOutside={(e) => e.preventDefault()}
        className={cn("border-l-4", home ? "border-l-riv" : "border-l-hil")}
      >
        {id && p ? (
          <div className="flex flex-col gap-6">
            <Button
              size="sm"
              variant={followed === id ? "primary" : "outline"}
              className="self-start"
              onClick={() => setPrefs({ player: followed === id ? null : id })}
              aria-pressed={followed === id}
            >
              <Star className="size-3.5" aria-hidden /> {followed === id ? t("Following") : t("Follow")}
            </Button>

            <section aria-label={t("Stats")}>
              <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-muted">{t("So far")}</h3>
              {stats ? <StatsGrid s={stats} /> : <p className="text-sm text-muted">{t("Loading…")}</p>}
            </section>

            {inMoment ? (
              <section aria-label={t("This moment")} className="rounded-xl border border-amber/40 bg-amber/5 p-3.5">
                <p className="text-xs font-medium text-amber">{t("In this moment")}</p>
                <p className="mt-1 font-display font-semibold tracking-tight">{tr(inMoment.moment.title)}</p>
                {w ? (
                  <p className="mt-1 text-sm">
                    <span className="num">{pct(w.actual.p_success)}</span>
                    <ArrowRight className="mx-1 inline size-3.5 text-muted" aria-hidden />
                    <span className="num text-green">{pct(w.counterfactual.p_success)}</span>{" "}
                    <span className="text-muted">{t("with {swap}", { swap: tr(w.counterfactual.profile.label) })}</span>
                  </p>
                ) : null}
              </section>
            ) : null}

            <section aria-label={t("Decisions")}>
              <h3 className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted">
                <Footprints className="size-3.5" aria-hidden />
                {fan ? t("The big calls") : t("Decisions that shaped the game")}
              </h3>
              {!decisions ? (
                <p className="text-sm text-muted">{t("Weighing every decision…")}</p>
              ) : decisions.items.length === 0 ? (
                <p className="rounded-xl border border-dashed border-line-2 p-4 text-sm text-muted">
                  {t("Nothing worth flagging yet: no costly choices and no standout one.")}
                </p>
              ) : (
                <ul className="flex flex-col gap-2.5">
                  {decisions.items.map((d) => (
                    <DecisionRow key={d.decision_id} d={d} fan={fan} live={live} />
                  ))}
                </ul>
              )}
              <p className="mt-3 text-[11px] leading-relaxed text-muted-2">
                {t("Ranked by the engine by goal odds, the chance the move ends in a goal.")}{" "}
                {decisions?.items.some((d) => d.source === "agents")
                  ? t("Lines written by the agents at the last whistle.")
                  : t("The agents rewrite these lines at half-time and full-time.")}
              </p>
            </section>
          </div>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
