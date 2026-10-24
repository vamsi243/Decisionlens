/** Match clock from milliseconds since kick-off: 45:00 + stoppage-free, so "67:12". */
export function clock(tMs: number): string {
  const s = Math.max(0, Math.floor(tMs / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export const pct = (p: number) => `${Math.round(p * 100)}%`;
export const kmh = (ms: number) => `${Math.round(ms * 3.6)} km/h`;
export const km = (m: number) => `${(m / 1000).toFixed(1)} km`;
export const minute = (tMs: number) => `${Math.floor(tMs / 60000) + 1}'`;

/** Pitch metres (origin bottom-left, y up) to SVG user units (y down). */
export const svgY = (y: number) => 68 - y;

export function surname(name: string): string {
  const parts = name.split(" ");
  return parts[parts.length - 1] ?? name;
}
