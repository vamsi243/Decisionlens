import type { KeyMoment } from "@/types/contracts";
import { frames } from "@/state/frames";
import { useMatch } from "@/state/match";
import { api } from "./api";

/**
 * Personal moment replays for the shared live broadcast: the viewer's own board plays the
 * moment's frames (from a few seconds before to a few after) at 10 Hz, holds on the option map,
 * then rejoins the live match. Nobody else's board moves.
 */
const HOLD_MS = 5000;
let timer: ReturnType<typeof setInterval> | undefined;
let hold: ReturnType<typeof setTimeout> | undefined;

export function stopClip() {
  clearInterval(timer);
  clearTimeout(hold);
  timer = hold = undefined;
  const s = useMatch.getState();
  s.setClip(null);
  s.pin(null);
}

export async function playClip(m: KeyMoment) {
  stopClip();
  const fs = await api.frames(m.moment_id, 1);
  if (!fs.length) return;
  const s = useMatch.getState();
  s.pin(m.moment_id);
  s.setClip({ momentId: m.moment_id, index: 0, total: fs.length });
  frames.speed = 1;
  let i = 0;
  timer = setInterval(() => {
    const f = fs[i];
    if (!f) {
      clearInterval(timer);
      hold = setTimeout(stopClip, HOLD_MS);
      return;
    }
    frames.push(f);
    useMatch.setState({ clockMs: f.t_ms, onPitch: f.players.map((p) => p.id) });
    useMatch.getState().setClip({ momentId: m.moment_id, index: i, total: fs.length });
    i += 1;
  }, 100);
}
