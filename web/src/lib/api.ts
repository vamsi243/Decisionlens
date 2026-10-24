import type {
  IntensityPoint,
  KeyMoment,
  MatchMeta,
  MatchStats,
  MomentAnalysis,
  Overlay,
  PlayerProfile,
  ReplayStatus,
  Speed,
  TrackingFrame,
  WorkloadState,
} from "@/types/contracts";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const WS_URL = `${API_URL.replace(/^http/, "ws")}/ws`;

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
  frames: (momentId: string, step = 1) =>
    req<TrackingFrame[]>(`/moments/${encodeURIComponent(momentId)}/frames?step=${step}`),
  recap: () => req<Overlay>("/recap"),
  stats: () => req<MatchStats>("/stats"),
  workload: () => req<WorkloadState[]>("/workload"),
  intensity: () => req<IntensityPoint[]>("/intensity"),
  play: () => post<ReplayStatus>("/replay/play"),
  pause: () => post<ReplayStatus>("/replay/pause"),
  seek: (t_ms: number) => post<ReplayStatus>("/replay/seek", { t_ms: Math.max(0, Math.round(t_ms)) }),
  speed: (speed: Speed) => post<ReplayStatus>("/replay/speed", { speed }),
};
