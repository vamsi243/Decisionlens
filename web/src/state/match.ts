import { create } from "zustand";
import type {
  Event,
  Hello,
  IntensityPoint,
  KeyMoment,
  MatchMeta,
  MatchStats,
  MomentAnalysis,
  Overlay,
  PlayerProfile,
  ReplayStatus,
  TrackingFrame,
  WorkloadState,
} from "@/types/contracts";
import { api } from "@/lib/api";
import { frames } from "./frames";

const CLOCK_EVERY_MS = 100; // real time between clock updates to React
const RECENT_EVENTS = 30;

interface MatchState {
  connected: boolean;
  meta: MatchMeta | null;
  players: Record<string, PlayerProfile>;
  status: ReplayStatus | null;
  clockMs: number;
  onPitch: string[];
  stats: MatchStats | null;
  workload: Record<string, WorkloadState>;
  intensity: IntensityPoint[];
  allMoments: KeyMoment[];
  seen: Record<string, KeyMoment>;
  analyses: Record<string, MomentAnalysis>;
  overlays: Record<string, Overlay>;
  noTranslation: boolean; // the server has no Translator key: cards stay in English
  events: Event[];
  pinned: string | null; // moment the user asked to replay / inspect

  setConnected: (c: boolean) => void;
  hello: (h: Hello) => void;
  frame: (f: TrackingFrame) => void;
  setStatus: (s: ReplayStatus) => void;
  setAllMoments: (m: KeyMoment[]) => void;
  moment: (m: KeyMoment) => void;
  analysis: (a: MomentAnalysis) => void;
  overlay: (o: Overlay) => void;
  setNoTranslation: (v: boolean) => void;
  event: (e: Event) => void;
  setStats: (s: MatchStats) => void;
  setWorkload: (w: WorkloadState[]) => void;
  setIntensity: (i: IntensityPoint[]) => void;
  pin: (id: string | null) => void;
}

let lastClockSet = 0;

export const useMatch = create<MatchState>((set, get) => ({
  connected: false,
  meta: null,
  players: {},
  status: null,
  clockMs: 0,
  onPitch: [],
  stats: null,
  workload: {},
  intensity: [],
  allMoments: [],
  seen: {},
  analyses: {},
  overlays: {},
  noTranslation: false,
  events: [],
  pinned: null,

  setConnected: (connected) => set({ connected }),

  hello: (h) => {
    frames.speed = h.status.speed;
    set({
      meta: h.meta,
      players: Object.fromEntries(h.players.map((p) => [p.player_id, p])),
      status: h.status,
      clockMs: h.status.t_ms,
      seen: Object.fromEntries(h.moments.map((m) => [m.moment_id, m])),
      stats: h.stats ?? null,
    });
    if (h.frame) get().frame(h.frame);
  },

  frame: (f) => {
    frames.push(f);
    const now = performance.now();
    const ids = f.players.map((p) => p.id);
    const changed = ids.join() !== get().onPitch.join();
    if (changed || now - lastClockSet > CLOCK_EVERY_MS) {
      lastClockSet = now;
      set(changed ? { clockMs: f.t_ms, onPitch: ids } : { clockMs: f.t_ms });
    }
  },

  setStatus: (status) => {
    frames.speed = status.speed;
    const seekedBack = status.t_ms < get().clockMs - 1000;
    set({
      status,
      clockMs: status.t_ms,
      events: seekedBack ? [] : get().events,
    });
  },

  setAllMoments: (allMoments) => set({ allMoments }),
  moment: (m) => set((s) => ({ seen: { ...s.seen, [m.moment_id]: m } })),
  analysis: (a) => set((s) => ({ analyses: { ...s.analyses, [a.moment.moment_id]: a } })),
  overlay: (o) =>
    set((s) => {
      const prev = s.overlays[o.overlay_id];
      // keep translations we already fetched when the English card is republished
      const text = { ...(o.text ?? {}) } as Record<string, Record<string, string>>;
      for (const [persona, langs] of Object.entries(prev?.text ?? {})) {
        text[persona] = { ...(langs as Record<string, string>), ...(text[persona] ?? {}) };
      }
      return { overlays: { ...s.overlays, [o.overlay_id]: { ...o, text } } };
    }),
  setNoTranslation: (noTranslation) => set({ noTranslation }),
  event: (e) => set((s) => ({ events: [...s.events.slice(-(RECENT_EVENTS - 1)), e] })),
  setStats: (stats) => set({ stats }),
  setWorkload: (w) =>
    set((s) => ({ workload: { ...s.workload, ...Object.fromEntries(w.map((x) => [x.player_id, x])) } })),
  setIntensity: (intensity) => set({ intensity }),
  pin: (pinned) => set({ pinned }),
}));

/**
 * Moments revealed so far: anything at or before the clock. A replay also knows every moment up
 * front (`allMoments`), so seeking forward still shows the earlier ones.
 */
export function revealedMoments(
  s: Pick<MatchState, "seen" | "allMoments" | "clockMs">,
): KeyMoment[] {
  const byId = new Map<string, KeyMoment>();
  for (const m of [...s.allMoments, ...Object.values(s.seen)]) byId.set(m.moment_id, m);
  return [...byId.values()].filter((m) => m.t_ms <= s.clockMs).sort((a, b) => a.t_ms - b.t_ms);
}

const requested = new Set<string>();
const translating = new Set<string>();

/** Fetch translations of the given cards (Azure AI Translator on the server, cached there). */
export function ensureTranslations(overlayIds: string[], lang: string) {
  const { overlays, overlay, noTranslation, setNoTranslation } = useMatch.getState();
  if (lang === "en" || noTranslation) return;
  for (const id of overlayIds) {
    const o = overlays[id];
    const key = `${id}:${lang}`;
    if (!o || translating.has(key) || o.text?.fan?.[lang]) continue;
    translating.add(key);
    api
      .overlay(id, lang)
      .then(overlay)
      .catch((e: Error) => {
        if (e.message.endsWith("503")) setNoTranslation(true);
        translating.delete(key);
      });
  }
}

/** Fetch analyses we have not received over the socket (e.g. moments before a seek). */
export function ensureAnalyses(moments: KeyMoment[]) {
  const { analyses, analysis } = useMatch.getState();
  for (const m of moments) {
    if (m.type === "fatigue_alert" || analyses[m.moment_id] || requested.has(m.moment_id)) continue;
    requested.add(m.moment_id);
    api
      .analysis(m.moment_id)
      .then(analysis)
      .catch(() => requested.delete(m.moment_id));
  }
}
