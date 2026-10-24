import { ArrowRight, RotateCcw } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import type { KeyMoment, MomentAnalysis, Persona, PlayerProfile, WorkloadState } from "@/types/contracts";
import { minute, pct, surname } from "@/lib/format";
import { MOMENT_LABEL } from "@/lib/moments";
import { cn } from "@/lib/utils";
import { replayMoment } from "./Scrubber";

interface Props {
  moment: KeyMoment;
  analysis?: MomentAnalysis;
  persona: Persona;
  players: Record<string, PlayerProfile>;
  workload: Record<string, WorkloadState>;
  active: boolean;
  favourite: boolean;
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

export function MomentCard({ moment, analysis, persona, players, workload, active, favourite }: Props) {
  const reduce = useReducedMotion();
  const w = analysis?.what_if;
  const opts = analysis?.options;
  const best = opts?.options.find((o) => o.option_id === opts.best_option_id);
  const chosen = opts?.options.find((o) => o.chosen);
  const actor = w ? players[w.actor_id] : players[moment.players[0] ?? ""];
  const fan = persona === "fan";
  const tired = moment.type === "fatigue_alert" ? workload[moment.players[0] ?? ""] : undefined;

  return (
    <motion.article
      layout={!reduce}
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        "rounded-lg border bg-surface p-4 shadow-sm transition-colors",
        active ? "border-amber/60 shadow-md" : "border-line",
        favourite && "ring-2 ring-amber/30",
      )}
    >
      <header className="flex items-center gap-2 text-xs text-muted">
        <span className="num text-amber">{minute(moment.t_ms)}</span>
        <span className="rounded-full bg-panel-2 px-2 py-0.5 font-medium text-ink">{MOMENT_LABEL[moment.type]}</span>
        <button
          type="button"
          onClick={() => void replayMoment(moment)}
          className="ml-auto inline-flex items-center gap-1 rounded-md px-1.5 py-1 hover:bg-panel-2 hover:text-ink"
          aria-label={`Replay ${moment.title}`}
        >
          <RotateCcw className="size-3.5" /> Replay
        </button>
      </header>
      <h3 className={cn("mt-2 font-display font-semibold tracking-tight", fan ? "text-lg" : "text-base")}>
        {moment.title}
      </h3>

      {tired ? (
        <p className="mt-2 text-sm text-muted">
          Fatigue <span className="num text-amber">{Math.round(tired.fatigue)}</span> / 100 ·{" "}
          {Math.round((1 - (tired.modifiers?.speed ?? 1)) * 100)}% off top speed
        </p>
      ) : null}

      {w ? (
        fan ? (
          <p className="mt-2 text-base leading-snug">
            {w.counterfactual.profile.label.replace(/ \(fresh sub\)$/, "")} would be{" "}
            <strong className={w.counterfactual.p_success >= w.actual.p_success ? "text-green" : "text-red"}>
              {swing(w.actual.p_success, w.counterfactual.p_success)}
            </strong>{" "}
            {VERB[moment.type] ?? "to come out on top"}.
          </p>
        ) : (
          <div className="mt-3 rounded-md bg-panel-2 p-3">
            <div className="flex items-baseline gap-2">
              <span className="num text-2xl font-medium">{pct(w.actual.p_success)}</span>
              <ArrowRight className="size-4 text-muted" aria-hidden />
              <span
                className={cn(
                  "num text-2xl font-medium",
                  w.counterfactual.p_success >= w.actual.p_success ? "text-green" : "text-red",
                )}
              >
                {pct(w.counterfactual.p_success)}
              </span>
            </div>
            <p className="num mt-1 text-xs text-muted-2">
              range {pct(w.actual.range.low)}–{pct(w.actual.range.high)} → {pct(w.counterfactual.range.low)}–
              {pct(w.counterfactual.range.high)}
            </p>
            <p className="mt-2 text-sm">
              {actor ? surname(actor.name) : "Actual"} vs {w.counterfactual.profile.label}
            </p>
            {w.drivers.length ? (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {w.drivers.map((d) => (
                  <li key={d.factor} className="num rounded-full border border-line bg-surface px-2 py-0.5 text-xs">
                    {d.text}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        )
      ) : null}

      {!fan && opts && best ? (
        <div className="mt-3 text-sm">
          <p className="text-muted">
            Best option:{" "}
            <span className="text-ink">
              {best.action}
              {best.target_id && players[best.target_id] ? ` to ${surname(players[best.target_id]!.name)}` : ""}
            </span>{" "}
            <span className="num text-green">{pct(best.p_success)}</span>
            {chosen && chosen.option_id !== best.option_id ? (
              <>
                {" "}· chosen <span className="num">{pct(chosen.p_success)}</span>
              </>
            ) : null}
          </p>
        </div>
      ) : null}

      {!analysis && moment.type !== "fatigue_alert" ? (
        <p className="mt-2 text-sm text-muted-2">Working out the options…</p>
      ) : null}
    </motion.article>
  );
}
