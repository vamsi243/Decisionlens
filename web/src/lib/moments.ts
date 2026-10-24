import type { KeyMoment, MomentAnalysis, MomentType } from "@/types/contracts";

/** How long a moment's option map / ghost stays on the board after it happens (match ms). */
export const SHOW_MS = 9000;

export const MOMENT_LABEL: Record<MomentType, string> = {
  aerial_duel: "Aerial duel",
  recovery_run: "Recovery run",
  big_chance: "Big chance",
  line_breaking_pass: "Line-breaking pass",
  press_turnover: "Press turnover",
  goal: "Goal",
  fatigue_alert: "Fatigue",
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
