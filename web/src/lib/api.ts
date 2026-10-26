import type {
  CalibrationReport,
  IntensityPoint,
  KeyMoment,
  MatchMeta,
  MatchStats,
  MomentAnalysis,
  Overlay,
  PlayerDecisions,
  PlayerProfile,
  PlayerStats,
  ReplayStatus,
  Speed,
  TrackingFrame,
  WorkloadState,
} from "@/types/contracts";

/**
 * Where the stream service lives. A deployed build reads it at runtime from `/config.json`
 * (written by the azd post-provision hook), so one build works anywhere; locally it falls back to
 * VITE_API_URL or localhost:8000.
 */
export let API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const wsUrl = () => `${API_URL.replace(/^http/, "ws")}/ws`;

export async function loadRuntimeConfig(): Promise<void> {
  // The deploy hook writes public/config.json with the Azure URL; local dev keeps VITE_API_URL.
  if (import.meta.env.DEV) return;
  try {
    const res = await fetch("/config.json", { cache: "no-store" });
    if (!res.ok) return;
    const cfg = (await res.json()) as { apiUrl?: string };
    if (cfg.apiUrl) API_URL = cfg.apiUrl.replace(/\/$/, "");
  } catch {
    /* no runtime config: keep the build-time default */
  }
}

export interface ServerConfig {
  live: boolean;
  signalr: boolean;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) throw new Error(`${init?.method ?? "GET"} ${path}: ${res.status}`);
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  config: () => req<ServerConfig>("/config"),
  negotiate: () => req<{ url: string; accessToken: string }>("/negotiate"),
  match: () => req<{ meta: MatchMeta; status: ReplayStatus }>("/match"),
  players: () => req<PlayerProfile[]>("/players"),
  moments: (all = false) => req<KeyMoment[]>(`/moments${all ? "?all=true" : ""}`),
  analysis: (id: string) => req<MomentAnalysis>(`/moments/${encodeURIComponent(id)}/analysis`),
  overlays: (all = false) => req<Overlay[]>(`/overlays${all ? "?all=true" : ""}`),
  overlay: (id: string, lang = "en") =>
    req<Overlay>(`/overlays/${encodeURIComponent(id)}?lang=${encodeURIComponent(lang)}`),
  heatmap: (id: string, full = false) =>
    req<{ nx: number; ny: number; cells: number[][] }>(
      `/players/${encodeURIComponent(id)}/heatmap${full ? "?full=true" : ""}`,
    ),
  playerStats: (id: string) => req<PlayerStats>(`/players/${encodeURIComponent(id)}/stats`),
  playerDecisions: (id: string) => req<PlayerDecisions>(`/players/${encodeURIComponent(id)}/decisions`),
  frames: (momentId: string, step = 1) =>
    req<TrackingFrame[]>(`/moments/${encodeURIComponent(momentId)}/frames?step=${step}`),
  recap: () => req<Overlay>("/recap"),
  translate: (lang: string, texts: string[]) => post<{ texts: string[] }>("/translate", { lang, texts }),
  stats: () => req<MatchStats>("/stats"),
  workload: () => req<WorkloadState[]>("/workload"),
  intensity: () => req<IntensityPoint[]>("/intensity"),
  calibration: () => req<CalibrationReport[]>("/calibration"),
  play: () => post<ReplayStatus>("/replay/play"),
  pause: () => post<ReplayStatus>("/replay/pause"),
  seek: (t_ms: number) => post<ReplayStatus>("/replay/seek", { t_ms: Math.max(0, Math.round(t_ms)) }),
  speed: (speed: Speed) => post<ReplayStatus>("/replay/speed", { speed }),
};
