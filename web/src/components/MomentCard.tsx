import { ArrowRight, BadgeCheck, Download, RotateCcw, Star } from "lucide-react";
import { downloadJson } from "@/lib/export";
import { motion, useReducedMotion } from "framer-motion";
import type {
  Driver,
  KeyMoment,
  Option,
  MomentAnalysis,
  Overlay,
  Persona,
  PlayerProfile,
  WorkloadState,
} from "@/types/contracts";
import { minute, pct, surname } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { MOMENT_LABEL } from "@/lib/moments";
import { useTr } from "@/lib/tr";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { replayMoment } from "./Scrubber";

interface Props {
  moment: KeyMoment;
  analysis?: MomentAnalysis;
  persona: Persona;
  players: Record<string, PlayerProfile>;
  workload: Record<string, WorkloadState>;
  active: boolean;
  favourite: boolean;
  overlay?: Overlay;
  lang: string;
}

/** The card text for this persona and language, falling back to English. */
export function narration(o: Overlay | undefined, persona: Persona, lang: string): string | null {
  const t = o?.text?.[persona];
  return t?.[lang] ?? t?.en ?? null;
}

export function SourceBadge({ overlay }: { overlay?: Overlay }) {
  const t = useT();
  if (!overlay) return null;
  const agents = overlay.source === "agents" || overlay.source === "mixed";
  return (
    <span
      className="inline-flex items-center gap-1 text-[11px] text-muted-2"
      title={
        agents
          ? t("Written by the agents; every number checked against the engine")
          : t("Written from engine numbers (no model call)")
      }
    >
      <BadgeCheck className="size-3 text-green" aria-hidden />
      {agents ? t("agents · grounded") : t("engine card")}
    </span>
  );
}

/** Plain-words strength of a change in probability, for fan cards (no new numbers). */
function swing(before: number, after: number): string {
  const d = after - before;
  if (d > 0.25) return "much more likely";
  if (d > 0.08) return "more likely";
  if (d > -0.08) return "about as likely";
  if (d > -0.25) return "less likely";
  return "much less likely";
}

const VERB: Partial<Record<KeyMoment["type"], string>> = {
  aerial_duel: "to win that header",
  recovery_run: "to catch the runner",
  big_chance: "to score",
  line_breaking_pass: "to find that pass",
  press_turnover: "to play out of the press",
  goal: "to score",
};

/** Whether a driver's change raises the chance: less reaction time or fatigue is better. */
function helps(d: Driver): boolean {
  return d.factor === "reaction" || d.factor === "fatigue" ? d.delta < 0 : d.delta > 0;
}

// Fan wording for each driver: [better, worse]. No numbers on fan cards.
const FAN_DRIVER: Record<string, [string, string]> = {
  jump_reach: ["longer reach", "shorter reach"],
  top_speed: ["faster", "slower"],
  acceleration: ["quicker off the mark", "slower off the mark"],
  reaction: ["sharper reactions", "slower reactions"],
  aerial: ["better in the air", "weaker in the air"],
  passing: ["a better passer", "a weaker passer"],
  finishing: ["a better finisher", "a weaker finisher"],
  fatigue: ["fresher legs", "more tired legs"],
};

const ACTION: Record<string, string> = {
  carry: "carry forward",
  clear: "clearance",
  recovery_run: "recovery run",
};

export interface Point {
  key: string;
  up: boolean;
  text: string;
}

/** Green and red points for a card, all from engine numbers: the swap's drivers, the options
 * (best vs chosen) and, for a fatigue alert, the player's state. */
export function bullets(
  moment: KeyMoment,
  analysis: MomentAnalysis | undefined,
  players: Record<string, PlayerProfile>,
  tired: WorkloadState | undefined,
  fan: boolean,
): Point[] {
  const out: Point[] = [];
  for (const d of analysis?.what_if?.drivers ?? []) {
    const up = helps(d);
    const words = FAN_DRIVER[d.factor];
    out.push({ key: d.factor, up, text: fan && words ? words[up ? 0 : 1] : d.text });
  }
  const opts = analysis?.options;
  const best = opts?.options.find((o) => o.option_id === opts.best_option_id);
  const chosen = opts?.options.find((o) => o.chosen);
  const name = (o: Option) =>
    `${ACTION[o.action] ?? o.action}${o.target_id && players[o.target_id] ? ` to ${surname(players[o.target_id]!.name)}` : ""}`;
  if (best && chosen && chosen.option_id === best.option_id) {
    out.push({ key: "best", up: true, text: fan ? "Picked the best option" : `Chose the best option: ${name(best)} · ${pct(best.p_success)}` });
  } else if (best) {
    out.push({ key: "best", up: true, text: fan ? `A ${name(best)} was on` : `Best: ${name(best)} · ${pct(best.p_success)}` });
    if (chosen) {
      out.push({ key: "chosen", up: false, text: fan ? `Went for a ${name(chosen)} instead` : `Chosen: ${name(chosen)} · ${pct(chosen.p_success)}` });
    }
  }
  if (moment.type === "fatigue_alert" && tired) {
    const loss = Math.round((1 - (tired.modifiers?.speed ?? 1)) * 100);
    if (fan) out.push({ key: "tired", up: false, text: "Running on empty" });
    else {
      out.push({ key: "fatigue", up: false, text: `Fatigue ${Math.round(tired.fatigue)} / 100` });
      if (loss > 0) out.push({ key: "speed", up: false, text: `${loss}% off top speed` });
    }
  }
  return out;
}

/** Green ▲ / red ▼ rows: what raised the chance and what lowered it. */
export function PointList({ points, fan, className }: { points: Point[]; fan: boolean; className?: string }) {
  const t = useT();
  const tr = useTr();
  if (!points.length) return null;
  return (
    <ul className={cn("space-y-1", className)} aria-label={t("What helped and what hurt")}>
      {points.map((b) => (
        <li
          key={b.key}
          className={cn(
            "flex items-start gap-2 rounded-md px-2 py-1 text-sm",
            b.up ? "bg-green/10 text-green" : "bg-red/10 text-red",
            fan && "text-base",
          )}
        >
          <span aria-hidden className="mt-[3px] text-[10px] leading-none">
            {b.up ? "▲" : "▼"}
          </span>
          <span className="sr-only">{b.up ? t("Raises the chance:") : t("Lowers the chance:")}</span>
          <span className="tabular-nums">{tr(b.text)}</span>
        </li>
      ))}
    </ul>
  );
}

const spread = (r: { low: number; high: number }) => pct(r.low) !== pct(r.high);

export function MomentCard({
  moment,
  analysis,
  persona,
  players,
  workload,
  active,
  favourite,
  overlay,
  lang,
}: Props) {
  const reduce = useReducedMotion();
  const w = analysis?.what_if;
  const actor = w ? players[w.actor_id] : players[moment.players[0] ?? ""];
  const fan = persona === "fan";
  const tired = moment.type === "fatigue_alert" ? workload[moment.players[0] ?? ""] : undefined;
  const text = narration(overlay, persona, lang);
  const points = bullets(moment, analysis, players, tired, fan);
  // The stripe shows whose decision the card is about: the what-if player's team, else the moment's.
  const teams = useMatch((s) => s.meta?.teams);
  const teamId = (w ? players[w.actor_id]?.team_id : undefined) ?? moment.team_id;
  const team = teams?.find((t) => t.team_id === teamId);
  const home = team !== undefined && team.team_id === teams?.[0]?.team_id;
  const setPrefs = usePrefs((s) => s.set);
  const followed = usePrefs((s) => s.player);
  const t = useT();
  const tr = useTr();

  if (fan) {
    const swingLine = w
      ? `${w.counterfactual.profile.label.replace(/ \(fresh sub\)$/, "")} would have been ${swing(w.actual.p_success, w.counterfactual.p_success)} ${VERB[moment.type] ?? "to come out on top"}.`
      : null;
    const star = actor && actor.player_id !== followed ? actor : null;
    return (
      <motion.article
        layout={!reduce}
        initial={reduce ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
        className={cn(
          "overflow-hidden rounded-2xl border bg-surface shadow-sm",
          active ? "border-amber/60 shadow-md" : "border-line",
          favourite && "ring-2 ring-amber/30",
        )}
      >
        <header
          className={cn(
            "flex items-center gap-2 px-4 py-2 text-xs font-medium",
            !team ? "bg-panel-2 text-muted" : home ? "bg-riv/10 text-riv-ink" : "bg-hil/20 text-hil-ink",
          )}
        >
          <span className="num">{minute(moment.t_ms)}</span>
          <span>{t(MOMENT_LABEL[moment.type])}</span>
          {team ? <span className="ml-auto">{team.name}</span> : null}
        </header>
        <div className="p-4">
          <h3 className="font-display text-xl font-semibold leading-snug tracking-tight">{tr(moment.title)}</h3>
          {text ? <p className="mt-2 text-base leading-snug text-ink/85">{text}</p> : null}
          {swingLine && !(text && text.includes(swing(w!.actual.p_success, w!.counterfactual.p_success))) ? (
            <p className="mt-3 rounded-lg bg-green/10 px-3 py-2 text-sm text-green">{tr(swingLine)}</p>
          ) : null}
          {points.length ? (
            <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("What helped and what hurt")}>
              {points.map((b) => (
                <li
                  key={b.key}
                  className={cn("rounded-full px-2.5 py-1 text-xs", b.up ? "bg-green/10 text-green" : "bg-red/10 text-red")}
                >
                  <span aria-hidden>{b.up ? "▲ " : "▼ "}</span>
                  {tr(b.text)}
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void replayMoment(moment)}
              className="inline-flex items-center gap-1.5 rounded-full bg-chrome px-3 py-1.5 text-xs font-medium text-white hover:bg-chrome/85"
            >
              <RotateCcw className="size-3.5" aria-hidden /> {t("Watch again")}
            </button>
            {star ? (
              <button
                type="button"
                onClick={() => setPrefs({ player: star.player_id, followCam: true })}
                className="inline-flex items-center gap-1.5 rounded-full border border-line-2 px-3 py-1.5 text-xs font-medium hover:bg-panel-2"
              >
                <Star className="size-3.5" aria-hidden /> {t("Follow {name}", { name: surname(star.name) })}
              </button>
            ) : null}
          </div>
        </div>
      </motion.article>
    );
  }

  return (
    <motion.article
      layout={!reduce}
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "rounded-lg border border-l-4 bg-surface p-4 shadow-sm transition-colors",
        active ? "border-amber/60 shadow-md" : "border-line",
        favourite && "ring-2 ring-amber/30",
        team ? (home ? "border-l-riv" : "border-l-hil") : "border-l-line-2",
      )}
    >
      <header className="flex items-center gap-2 text-xs text-muted">
        <span className="num text-amber">{minute(moment.t_ms)}</span>
        <span className="rounded-full bg-panel-2 px-2 py-0.5 font-medium text-ink">{t(MOMENT_LABEL[moment.type])}</span>
        {team ? (
          <span className={cn("font-medium", home ? "text-riv-ink" : "text-hil-ink")}>{team.short_name}</span>
        ) : null}
        <button
          type="button"
          onClick={() => void replayMoment(moment)}
          className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-panel-2 hover:text-ink"
          aria-label={t("Replay {moment}", { moment: tr(moment.title) })}
        >
          <RotateCcw className="size-3.5" /> {t("Replay")}
        </button>
      </header>
      <h3 className={cn("mt-2 font-display font-semibold tracking-tight", fan ? "text-lg" : "text-base")}>
        {tr(moment.title)}
      </h3>

      {w && !fan ? (
        <div className="mt-3">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="num text-2xl font-medium">{pct(w.actual.p_success)}</span>
            <ArrowRight className="size-4 self-center text-muted" aria-hidden />
            <span
              className={cn(
                "num text-2xl font-medium",
                w.counterfactual.p_success >= w.actual.p_success ? "text-green" : "text-red",
              )}
            >
              {pct(w.counterfactual.p_success)}
            </span>
            <span className="text-xs text-muted">
              {actor ? surname(actor.name) : t("Actual")} → {tr(w.counterfactual.profile.label)}
            </span>
          </div>
          {spread(w.actual.range) || spread(w.counterfactual.range) ? (
            <p className="num mt-0.5 text-xs text-muted-2">
              {t("range {from} → {to}", {
                from: `${pct(w.actual.range.low)}–${pct(w.actual.range.high)}`,
                to: `${pct(w.counterfactual.range.low)}–${pct(w.counterfactual.range.high)}`,
              })}
            </p>
          ) : null}
        </div>
      ) : null}

      {fan ? (
        text ? (
          <p className="mt-2 text-base leading-snug">{text}</p>
        ) : w ? (
          <p className="mt-2 text-base leading-snug">
            {w.counterfactual.profile.label.replace(/ \(fresh sub\)$/, "")} would be{" "}
            <strong className={w.counterfactual.p_success >= w.actual.p_success ? "text-green" : "text-red"}>
              {swing(w.actual.p_success, w.counterfactual.p_success)}
            </strong>{" "}
            {VERB[moment.type] ?? "to come out on top"}.
          </p>
        ) : null
      ) : null}

      <PointList points={points} fan={fan} className="mt-3" />

      {text && !fan ? (
        <details className="mt-3" open={lang !== "en"}>
          <summary className="cursor-pointer select-none text-xs font-medium text-muted hover:text-ink">
            {t("Read the analysis")}
          </summary>
          <p className="mt-1.5 text-sm leading-relaxed text-ink/85">{text}</p>
        </details>
      ) : null}

      {!analysis && moment.type !== "fatigue_alert" ? (
        <p className="mt-2 text-sm text-muted-2">{t("Working out the options…")}</p>
      ) : null}
      <footer className="mt-3 flex items-center justify-between gap-2">
        {!fan && (overlay || analysis) ? (
          <button
            type="button"
            onClick={() =>
              downloadJson(`decision-lens_${moment.moment_id}.json`, overlay ?? analysis)
            }
            className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-muted hover:bg-panel-2 hover:text-ink"
            aria-label={t("Export overlay JSON for {moment}", { moment: tr(moment.title) })}
          >
            <Download className="size-3" aria-hidden /> {t("Overlay JSON")}
          </button>
        ) : (
          <span />
        )}
        <SourceBadge overlay={overlay} />
      </footer>
    </motion.article>
  );
}
