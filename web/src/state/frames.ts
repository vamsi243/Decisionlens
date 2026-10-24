import type { TrackingFrame } from "@/types/contracts";

/**
 * Frames live outside React: at 8x they arrive 80 times a second, and the board reads them in a
 * requestAnimationFrame loop. We keep the last two contiguous frames and glide from one to the
 * other over one frame interval (100 ms / speed), which gives smooth 60 fps motion at the cost of
 * one frame of latency. A jump (seek, gap) snaps instead of sweeping across the pitch.
 */

export interface PlayerSample {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

export interface Sample {
  frame: number;
  tMs: number;
  players: Map<string, PlayerSample>;
  ball: { x: number; y: number; z: number };
  owner: string | null;
  trail: { x: number; y: number }[];
}

const TRAIL = 8;
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

class FrameBuffer {
  private prev: TrackingFrame | null = null;
  private cur: TrackingFrame | null = null;
  private arrival = 0;
  private trail: { x: number; y: number }[] = [];
  speed = 1;
  smooth = true;

  push(f: TrackingFrame) {
    const contiguous = this.cur !== null && f.frame === this.cur.frame + 1;
    this.prev = contiguous ? this.cur : f;
    this.cur = f;
    this.arrival = performance.now();
    if (!contiguous) this.trail = [];
    this.trail.push({ x: f.ball.x, y: f.ball.y });
    if (this.trail.length > TRAIL) this.trail.shift();
  }

  get latest(): TrackingFrame | null {
    return this.cur;
  }

  sample(now: number): Sample | null {
    const cur = this.cur;
    const prev = this.prev ?? cur;
    if (!cur || !prev) return null;
    const interval = 100 / Math.max(1, this.speed);
    const t = this.smooth ? Math.min(1, Math.max(0, (now - this.arrival) / interval)) : 1;
    const before = new Map(prev.players.map((p) => [p.id, p]));
    const players = new Map<string, PlayerSample>();
    for (const p of cur.players) {
      const a = before.get(p.id) ?? p;
      players.set(p.id, {
        x: lerp(a.x, p.x, t),
        y: lerp(a.y, p.y, t),
        vx: lerp(a.vx, p.vx, t),
        vy: lerp(a.vy, p.vy, t),
      });
    }
    return {
      frame: cur.frame,
      tMs: lerp(prev.t_ms, cur.t_ms, t),
      players,
      ball: {
        x: lerp(prev.ball.x, cur.ball.x, t),
        y: lerp(prev.ball.y, cur.ball.y, t),
        z: lerp(prev.ball.z, cur.ball.z, t),
      },
      owner: cur.ball.owner_id ?? null,
      trail: this.trail,
    };
  }
}

export const frames = new FrameBuffer();
