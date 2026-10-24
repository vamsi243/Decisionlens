import type { KeyMoment, MomentAnalysis, MomentType } from "@/types/contracts";
import { msg } from "./i18n";

/** How long a moment's option map / ghost stays on the board after it happens (match ms). */
export const SHOW_MS = 9000;

export const MOMENT_LABEL: Record<MomentType, string> = {
  aerial_duel: msg("Aerial duel"),
  recovery_run: msg("Recovery run"),
  big_chance: msg("Big chance"),
  line_breaking_pass: msg("Line-breaking pass"),
  press_turnover: msg("Press turnover"),
  goal: msg("Goal"),
  fatigue_alert: msg("Fatigue"),
};

/** The moment the board should illustrate right now, if any. */
export function activeMoment(
  seen: Record<string, KeyMoment>,
  analyses: Record<string, MomentAnalysis>,
  clockMs: number,
  pinned: string | null,
): MomentAnalysis | null {
  if (pinned && analyses[pinned]) {
    const a = analyses[pinned];
    if (clockMs >= a.moment.frame_range.start * 100 - 500) return a;
  }
  let best: MomentAnalysis | null = null;
  for (const m of Object.values(seen)) {
    const a = analyses[m.moment_id];
    if (!a || m.type === "fatigue_alert") continue;
    if (m.t_ms <= clockMs && clockMs < m.t_ms + SHOW_MS && (!best || m.t_ms > best.moment.t_ms)) {
      best = a;
    }
  }
  return best;
}
