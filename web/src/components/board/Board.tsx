import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { frames } from "@/state/frames";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { activeMoment } from "@/lib/moments";
import { km, kmh, surname, svgY } from "@/lib/format";
import { ArrowMarkers, MomentLayer } from "./MomentLayer";
import { PITCH, PitchMarkings } from "./Pitch";

const SPRINT = 7.0; // m/s: the speed badge appears above this (25 km/h)
const R = 1.15; // player disc radius, metres
const TRAIL = 8;
const DISTANCE_BADGE_MS = 4000;

interface Refs {
  group: SVGGElement | null;
  badge: SVGGElement | null;
  badgeText: SVGTextElement | null;
}

/** Name tag + distance badges driven by React (they change rarely). */
function useDistanceBadges() {
  const workload = useMatch((s) => s.workload);
  const lastKm = useRef(new Map<string, number>());
  const [badges, setBadges] = useState<Record<string, { label: string; until: number }>>({});
  useEffect(() => {
    const now = performance.now();
    const fresh: Record<string, { label: string; until: number }> = {};
    for (const w of Object.values(workload)) {
      const whole = Math.floor(w.distance_m / 1000);
      const before = lastKm.current.get(w.player_id);
      lastKm.current.set(w.player_id, whole);
      if (before !== undefined && whole > before) {
        fresh[w.player_id] = { label: km(whole * 1000), until: now + DISTANCE_BADGE_MS };
      }
    }
    if (Object.keys(fresh).length) setBadges((b) => ({ ...b, ...fresh }));
  }, [workload]);
  useEffect(() => {
    const t = setInterval(() => {
      const now = performance.now();
      setBadges((b) => {
        const kept = Object.fromEntries(Object.entries(b).filter(([, v]) => v.until > now));
        return Object.keys(kept).length === Object.keys(b).length ? b : kept;
      });
    }, 500);
    return () => clearInterval(t);
  }, []);
  return badges;
}

export function Board() {
  const onPitch = useMatch((s) => s.onPitch);
  const players = useMatch((s) => s.players);
  const home = useMatch((s) => s.meta?.teams[0]?.team_id);
  const seen = useMatch((s) => s.seen);
  const analyses = useMatch((s) => s.analyses);
  const clockMs = useMatch((s) => s.clockMs);
  const pinned = useMatch((s) => s.pinned);
  const focus = usePrefs((s) => s.player);
  const reduce = useReducedMotion();
  const distanceBadges = useDistanceBadges();

  const active = activeMoment(seen, analyses, clockMs, pinned);
  const involved = useMemo(() => new Set(active?.moment.players ?? []), [active]);

  const refs = useRef(new Map<string, Refs>());
  const ball = useRef<SVGCircleElement | null>(null);
  const shadow = useRef<SVGEllipseElement | null>(null);
  const trail = useRef<(SVGCircleElement | null)[]>([]);

  useEffect(() => {
    frames.smooth = !reduce;
  }, [reduce]);

  useEffect(() => {
    let raf = 0;
    const tick = (now: number) => {
      const s = frames.sample(now);
      if (s) {
        for (const [id, p] of s.players) {
          const r = refs.current.get(id);
          if (!r?.group) continue;
          r.group.setAttribute("transform", `translate(${p.x.toFixed(2)} ${svgY(p.y).toFixed(2)})`);
          const speed = Math.hypot(p.vx, p.vy);
          if (r.badge && r.badgeText) {
            const show = speed > SPRINT;
            r.badge.style.opacity = show ? "1" : "0";
            if (show) r.badgeText.textContent = kmh(speed);
          }
        }
        const lift = s.ball.z * 0.09;
        ball.current?.setAttribute("cx", s.ball.x.toFixed(2));
        ball.current?.setAttribute("cy", (svgY(s.ball.y) - lift).toFixed(2));
        ball.current?.setAttribute("r", (0.55 + lift * 0.35).toFixed(2));
        shadow.current?.setAttribute("cx", s.ball.x.toFixed(2));
        shadow.current?.setAttribute("cy", (svgY(s.ball.y) + 0.25).toFixed(2));
        shadow.current?.setAttribute("opacity", Math.max(0.05, 0.25 - s.ball.z * 0.02).toFixed(2));
        for (let i = 0; i < TRAIL; i++) {
          const el = trail.current[i];
          const pt = s.trail[s.trail.length - 1 - i];
          if (!el) continue;
          if (pt && i > 0) {
            el.setAttribute("cx", pt.x.toFixed(2));
            el.setAttribute("cy", svgY(pt.y).toFixed(2));
            el.setAttribute("opacity", ((1 - i / TRAIL) * 0.35).toFixed(2));
          } else el.setAttribute("opacity", "0");
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-panel-2 shadow-md">
      <svg
        viewBox={`-3 -3 ${PITCH.length + 6} ${PITCH.width + 6}`}
        className="block h-auto w-full select-none"
        role="img"
        aria-label="Live tactics board"
      >
        <ArrowMarkers />
        <PitchMarkings />
        <MomentLayer analysis={active} />
        {Array.from({ length: TRAIL }, (_, i) => (
          <circle key={i} ref={(el) => (trail.current[i] = el)} r={0.35} fill="var(--amber)" opacity={0} />
        ))}
        {onPitch.map((id) => {
          const p = players[id];
          if (!p) return null;
          const isHome = p.team_id === home;
          const focused = id === focus;
          const tagged = focused || involved.has(id) || id in distanceBadges;
          return (
            <g
              key={id}
              ref={(el) => {
                const r = refs.current.get(id) ?? { group: null, badge: null, badgeText: null };
                r.group = el;
                refs.current.set(id, r);
              }}
            >
              {focused ? <circle r={R * 2.4} fill="var(--amber)" opacity={0.16} /> : null}
              {involved.has(id) ? (
                <circle r={R * 1.75} fill="none" stroke="var(--amber)" strokeWidth={0.18} />
              ) : null}
              <circle
                r={R}
                fill={isHome ? "var(--ink)" : "var(--surface)"}
                stroke="var(--ink)"
                strokeWidth={isHome ? 0 : 0.28}
              />
              <text
                y={0.4}
                textAnchor="middle"
                fontSize={1.08}
                className="num"
                fontWeight={500}
                fill={isHome ? "var(--surface)" : "var(--ink)"}
              >
                {p.shirt_number}
              </text>
              {tagged ? (
                <g transform={`translate(0 ${-R - 1.3})`}>
                  <text textAnchor="middle" fontSize={1.3} fontWeight={600} fill="var(--ink)" stroke="var(--panel-2)" strokeWidth={0.5} paintOrder="stroke">
                    {surname(p.name)}
                    {distanceBadges[id] ? ` · ${distanceBadges[id].label}` : ""}
                  </text>
                </g>
              ) : null}
              <g
                ref={(el) => {
                  const r = refs.current.get(id) ?? { group: null, badge: null, badgeText: null };
                  r.badge = el;
                  refs.current.set(id, r);
                }}
                transform={`translate(${R + 0.4} ${R + 0.2})`}
                style={{ opacity: 0, transition: "opacity 200ms var(--ease)" }}
              >
                <rect x={0} y={-0.95} width={5.6} height={1.7} rx={0.85} fill="var(--amber)" />
                <text
                  ref={(el) => {
                    const r = refs.current.get(id) ?? { group: null, badge: null, badgeText: null };
                    r.badgeText = el;
                    refs.current.set(id, r);
                  }}
                  x={2.8}
                  y={0.32}
                  textAnchor="middle"
                  fontSize={0.95}
                  className="num"
                  fill="var(--surface)"
                />
              </g>
            </g>
          );
        })}
        <ellipse ref={shadow} rx={0.6} ry={0.25} fill="var(--ink)" opacity={0.2} />
        <circle ref={ball} r={0.55} fill="var(--amber)" stroke="var(--surface)" strokeWidth={0.12} />
      </svg>
      {onPitch.length === 0 ? (
        <div className="absolute inset-0 grid place-items-center text-sm text-muted">Waiting for the stream…</div>
      ) : null}
    </div>
  );
}
