import { Download, RotateCcw, Star } from "lucide-react";
import { useState } from "react";
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
import { midSentence, minute, pct, surname } from "@/lib/format";
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
      className="text-[11px] text-muted-2"
      title={
        agents
          ? t("Written by the agents; every number checked against the engine")
          : t("Written from engine numbers (no model call)")
      }
    >
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
      // A riskier choice can still be the more dangerous one: say so, so "chosen" isn't read as
      // simply wrong. Both threat gains come from the engine's xT model.
      const ratio = best.xt_gain > 0 ? chosen.xt_gain / best.xt_gain : 0;
      if (chosen.xt_gain > 0 && (best.xt_gain <= 0 || ratio >= 1.5)) {
        out.push({
          key: "threat",
          up: true,
          text: fan
            ? "It was the most dangerous option"
            : best.xt_gain > 0
              ? `But it carried ${Math.round(ratio)}× the threat of the best option`
              : "But it was the only option that added threat",
        });
      }
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

/** The agent's explanation under a hairline: three lines, then "More" to read the rest. */
function AgentLine({ text }: { text: string }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3 border-t border-line pt-3">
      <p className={cn("text-sm leading-relaxed text-muted", !open && "line-clamp-3")}>{text}</p>
      {text.length > 180 ? (
        <button type="button" onClick={() => setOpen((o) => !o)} className="mt-1 text-xs font-medium text-ink hover:underline">
          {open ? t("Less") : t("More")}
        </button>
      ) : null}
    </div>
  );
}

/** Green ▲ / red ▼ rows: what raised the chance and what lowered it. `plain` drops the tint
 * behind each row (the moment card's list style). */
export function PointList({
  points,
  fan,
  plain = false,
  className,
}: {
  points: Point[];
  fan: boolean;
  plain?: boolean;
  className?: string;
}) {
  const t = useT();
  const tr = useTr();
  if (!points.length) return null;
  return (
    <ul className={cn("space-y-1", className)} aria-label={t("What helped and what hurt")}>
      {points.map((b) => (
        <li
          key={b.key}
          className={cn(
            "flex items-start gap-2 text-sm",
            plain ? "py-0.5" : "rounded-md px-2 py-1",
            b.up ? (plain ? "text-green" : "bg-green/10 text-green") : plain ? "text-red" : "bg-red/10 text-red",
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
  // The swap moves the chance by less than a rounded point: show it as no change, not a gain.
  const same = w ? pct(w.actual.p_success) === pct(w.counterfactual.p_success) : false;
  // The stripe shows whose decision the card is about: the what-if player's team, else the moment's.
  const teams = useMatch((s) => s.meta?.teams);
  const teamId = (w ? players[w.actor_id]?.team_id : undefined) ?? moment.team_id;
  const team = teams?.find((t) => t.team_id === teamId);
  const home = team !== undefined && team.team_id === teams?.[0]?.team_id;
  const setPrefs = usePrefs((s) => s.set);
  const followed = usePrefs((s) => s.follow);
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
          "rounded-2xl border bg-surface p-5 shadow-sm",
          active ? "border-key/60 shadow-md" : "border-line",
          favourite && "ring-2 ring-key/30",
        )}
      >
        <header className="flex items-center gap-2 text-xs text-muted">
          <span className="rounded-full bg-key-bright px-2.5 py-1 font-semibold text-chrome">
            {t(MOMENT_LABEL[moment.type])} · <span className="num">{minute(moment.t_ms)}</span>
          </span>
          {team ? (
            <span className="inline-flex items-center gap-1.5">
              <span className={cn("size-2 rounded-[2px]", home ? "bg-riv" : "bg-hil")} aria-hidden />
              {team.name}
            </span>
          ) : null}
        </header>
        <div className="mt-3">
          <h3 className="font-display text-2xl font-extrabold leading-tight tracking-tight text-chrome">{tr(moment.title)}</h3>
          {text ? <p className="mt-2 text-base leading-snug text-ink/85">{text}</p> : null}
          {swingLine && !(text && text.includes(swing(w!.actual.p_success, w!.counterfactual.p_success))) ? (
            <p className="mt-3 rounded-lg bg-green/10 px-3 py-2 text-sm text-green">{tr(swingLine)}</p>
          ) : null}
          <PointList points={points} fan plain className="mt-3" />
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
                onClick={() => setPrefs({ follow: star.player_id, followCam: true })}
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
        "rounded-2xl border bg-surface p-5 shadow-sm transition-colors",
        active ? "border-key/60 shadow-md" : "border-line",
        favourite && "ring-2 ring-key/30",
      )}
    >
      <header className="flex items-center gap-2 text-xs text-muted">
        <span className="rounded-full bg-key-bright px-2.5 py-1 font-semibold text-chrome">
          {t(MOMENT_LABEL[moment.type])} · <span className="num">{minute(moment.t_ms)}</span>
        </span>
        {team ? (
          <span className="inline-flex items-center gap-1.5">
            <span className={cn("size-2 rounded-[2px]", home ? "bg-riv" : "bg-hil")} aria-hidden />
            {team.short_name}
          </span>
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
      <h3 className="mt-3 font-display text-2xl font-extrabold leading-tight tracking-tight text-chrome">
        {tr(moment.title)}
      </h3>

      {w ? (
        <div className="mt-3">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-display text-4xl font-black leading-none tabular-nums">{pct(w.actual.p_success)}</span>
            <span className="text-xl text-muted" aria-hidden>→</span>
            <span
              className={cn(
                "font-display text-4xl font-black leading-none tabular-nums",
                same ? "text-ink" : w.counterfactual.p_success > w.actual.p_success ? "text-green" : "text-red",
              )}
            >
              {pct(w.counterfactual.p_success)}
            </span>
            <span className="text-sm text-muted">
              {t("with {swap}", { swap: tr(midSentence(w.counterfactual.profile.label)) })}
            </span>
            {same ? (
              <span className="rounded-full bg-panel-2 px-2 py-0.5 text-xs font-medium text-muted">{t("no real change")}</span>
            ) : null}
          </div>
          {spread(w.actual.range) || spread(w.counterfactual.range) ? (
            <p className="num mt-1.5 text-xs text-muted-2">
              {t("range {from} → {to}", {
                from: `${pct(w.actual.range.low)}–${pct(w.actual.range.high)}`,
                to: `${pct(w.counterfactual.range.low)}–${pct(w.counterfactual.range.high)}`,
              })}
            </p>
          ) : null}
        </div>
      ) : null}

      <PointList points={points} fan={false} plain className="mt-3" />

      {text ? <AgentLine text={text} /> : null}

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
