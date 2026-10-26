import { create } from "zustand";
import type { KeyMoment, TrackingFrame } from "@/types/contracts";
import { frames } from "@/state/frames";
import { useMatch } from "@/state/match";
import { api } from "./api";

/**
 * Personal moment replays for the shared live broadcast: the viewer's own board plays the
 * moment's frames (from a few seconds before to a few after) at 10 Hz, holds on the option map,
 * then rejoins the live match. Nobody else's board moves.
 */
const HOLD_MS = 5000;
const RETRY_MS = 1500; // a container waking from zero can drop the first request
const FAILED_MS = 4000;
let timer: ReturnType<typeof setInterval> | undefined;
let hold: ReturnType<typeof setTimeout> | undefined;
let request = 0; // only the latest click may start a clip

/** What the Replay button for a moment should show while its frames load, or if they can't. */
export const useReplay = create<{ id: string | null; state: "loading" | "failed" | null }>(() => ({
  id: null,
  state: null,
}));

export function replayState(id: string): "loading" | "failed" | null {
  const r = useReplay.getState();
  return r.id === id ? r.state : null;
}

export function stopClip() {
  clearInterval(timer);
  clearTimeout(hold);
  timer = hold = undefined;
  const s = useMatch.getState();
  s.setClip(null);
  s.pin(null);
}

async function load(id: string): Promise<TrackingFrame[]> {
  try {
    return await api.frames(id, 1);
  } catch {
    await new Promise((r) => setTimeout(r, RETRY_MS));
    return api.frames(id, 1);
  }
}

export async function playClip(m: KeyMoment) {
  const mine = ++request;
  stopClip();
  useReplay.setState({ id: m.moment_id, state: "loading" });
  let fs: TrackingFrame[] = [];
  try {
    fs = await load(m.moment_id);
  } catch {
    fs = [];
  }
  if (mine !== request) return; // a newer click took over
  if (!fs.length) {
    useReplay.setState({ id: m.moment_id, state: "failed" });
    setTimeout(() => {
      if (replayState(m.moment_id) === "failed") useReplay.setState({ id: null, state: null });
    }, FAILED_MS);
    return;
  }
  useReplay.setState({ id: null, state: null });
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
