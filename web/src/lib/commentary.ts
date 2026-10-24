import type { Event, PlayerProfile, TeamMeta } from "@/types/contracts";
import { surname } from "./format";

/**
 * One-line live commentary for fans, written from engine events by templates (no model, no
 * numbers beyond the minute). Returns null for the routine stuff (passes, pressure).
 */
export function commentary(
  e: Event,
  players: Record<string, PlayerProfile>,
  teams: TeamMeta[] | undefined,
): string | null {
  const who = (id?: string | null) => (id && players[id] ? surname(players[id]!.name) : "someone");
  const team = (id?: string | null) => teams?.find((t) => t.team_id === id)?.name ?? "";
  const p = who(e.player_id);
  const t = who(e.target_id);
  const ok = e.outcome === "success";
  switch (e.type) {
    case "goal":
      return `GOAL! ${p} scores for ${team(e.team_id)}!`;
    case "shot":
      if (ok) return null; // the goal event says it
      return (e.tags ?? []).includes("saved") ? `${p} shoots… saved!` : `${p} fires wide`;
    case "tackle":
      return ok ? `${p} wins it back with a tackle on ${t}` : null;
    case "interception":
      return `${p} reads it and steps in`;
    case "aerial_duel":
      return ok ? `${p} wins the header` : `${t} beats ${p} in the air!`;
    case "dribble":
      return ok ? `${p} skips past ${t}` : `${t} stops ${p} dead`;
    case "cross":
      return `${p} whips in a cross`;
    case "clearance":
      return `${p} clears the danger`;
    case "foul":
      return `Foul by ${p} on ${t}`;
    case "substitution":
      return `Change for ${team(e.team_id)}: ${p} on, ${t} off`;
    case "pass":
      return ok && (e.tags ?? []).includes("lofted") ? `${p} switches play to ${t}` : null;
    case "period_end":
      return e.period === "1H" ? "Half-time" : "Full-time";
    default:
      return null;
  }
}
