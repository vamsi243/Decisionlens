import { useReducedMotion } from "framer-motion";
import { Flame } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { frames } from "@/state/frames";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { useT } from "@/lib/i18n";
import { useUi } from "@/state/ui";
import type { PlayerStats } from "@/types/contracts";
import { activeMoment } from "@/lib/moments";
import { km, kmh, surname, svgY } from "@/lib/format";
import { CamToggle, MomentBanner, PlayerCard } from "../fan/FanOverlays";
import { ArrowMarkers, MomentLayer } from "./MomentLayer";
import { DISC, NameTag, PITCH, PitchMarkings, PitchSurface, PlayerDisc } from "./Pitch";

// The whole pitch with a 3 m run-off, and the follow-cam's zoomed width (metres).
const FULL_VIEW = [-3, -3, PITCH.length + 6, PITCH.width + 6];
const CAM_WIDTH = 48;
const CAM_EASE = 0.08; // share of the gap closed per animation frame
const SPRINT = 7.0; // m/s: the speed badge appears above this (25 km/h)
const R = DISC;
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

const HEAT_REFRESH_MS = 10_000;

/** Where the followed player has spent the match so far (analyst view). */
function HeatLayer({ playerId }: { playerId: string }) {
  const [cells, setCells] = useState<number[][] | null>(null);
  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .heatmap(playerId)
        .then((h) => alive && setCells(h.cells))
        .catch(() => undefined);
    void load();
    const t = setInterval(load, HEAT_REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [playerId]);
  if (!cells) return null;
  const nx = cells.length;
  const ny = cells[0]?.length ?? 1;
  const max = Math.max(1e-6, ...cells.flat());
  const w = PITCH.length / nx;
  const h = PITCH.width / ny;
  return (
    <g aria-hidden>
      {cells.flatMap((col, i) =>
        col.map((v, j) =>
          v > 0 ? (
            <rect
              key={`${i}-${j}`}
              x={i * w}
              y={PITCH.width - (j + 1) * h}
              width={w}
              height={h}
              fill="var(--heat)"
              opacity={0.08 + 0.55 * (v / max)}
            />
          ) : null,
        ),
      )}
    </g>
  );
}

/** What shows when you hover a player: live workload at once, event counts a moment later. */
function HoverCard({ id }: { id: string }) {
  const p = useMatch((s) => s.players[id]);
  const w = useMatch((s) => s.workload[id]);
  const home = useMatch((s) => s.meta?.teams[0]?.team_id);
  const [stats, setStats] = useState<PlayerStats | null>(null);
  const t = useT();
  useEffect(() => {
    let alive = true;
    void api
      .playerStats(id)
      .then((s) => alive && setStats(s))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [id]);
  if (!p) return null;
  const loss = w ? Math.round((1 - (w.modifiers?.speed ?? 1)) * 100) : 0;
  const rows: [string, string][] = [
    ["Distance", w ? km(w.distance_m) : "–"],
    ["Fatigue", w ? `${Math.round(w.fatigue)} / 100` : "–"],
    ["Sprints", w ? String(w.sprints) : "–"],
    ["Top speed", loss ? `−${loss}%` : t("full")],
  ];
  if (stats) {
    rows.push(["Passes", `${stats.passes_completed ?? 0} / ${stats.passes ?? 0}`]);
    if (stats.shots) rows.push(["Shots · goals", `${stats.shots} · ${stats.goals ?? 0}`]);
    if (stats.tackles) rows.push(["Tackles won", `${stats.tackles_won ?? 0} / ${stats.tackles}`]);
    if (stats.aerial_duels) rows.push(["Aerials won", `${stats.aerial_won ?? 0} / ${stats.aerial_duels}`]);
    if (stats.interceptions) rows.push(["Interceptions", String(stats.interceptions)]);
  }
  return (
    <div className="w-52 rounded-xl border border-line bg-surface/95 p-3 text-xs shadow-lg backdrop-blur">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <span
          className={cn(
            "num grid size-5 place-items-center rounded-full text-[10px]",
            p.team_id === home ? "bg-riv text-white" : "bg-hil text-hil-ink",
          )}
        >
          {p.shirt_number}
        </span>
        {p.name}
      </p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{t(k)}</dt>
            <dd className={cn("num text-right", k === "Fatigue" && w && w.fatigue >= 70 && "text-amber")}>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-muted-2">{t("Click for their key decisions")}</p>
    </div>
  );
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
  const persona = usePrefs((s) => s.persona);
  const [heat, setHeat] = useState(false);
  const openPanel = useUi((s) => s.openPanel);
  const t = useT();
  const setPrefs = usePrefs((s) => s.set);
  const [hover, setHover] = useState<string | null>(null);
  const hoverRef = useRef<string | null>(null);
  const box = useRef<HTMLDivElement | null>(null);
  const card = useRef<HTMLDivElement | null>(null);
  hoverRef.current = hover;
  const reduce = useReducedMotion();
  const distanceBadges = useDistanceBadges();

  const active = activeMoment(seen, analyses, clockMs, pinned);
  const involved = useMemo(() => new Set(active?.moment.players ?? []), [active]);

  const refs = useRef(new Map<string, Refs>());
  const ball = useRef<SVGCircleElement | null>(null);
  const shadow = useRef<SVGEllipseElement | null>(null);
  const trail = useRef<(SVGCircleElement | null)[]>([]);
  // Follow-cam (fan mode): the viewBox glides to keep the followed player in frame.
  const svg = useRef<SVGSVGElement | null>(null);
  const followCam = usePrefs((s) => s.followCam);
  const fan = persona === "fan";
  const cam = useRef({ on: false, id: null as string | null, reduce: false });
  cam.current = { on: fan && followCam && !!focus, id: focus, reduce: !!reduce };
  const view = useRef<number[]>([...FULL_VIEW]);

  useEffect(() => {
    frames.smooth = !reduce;
  }, [reduce]);

  useEffect(() => {
    let raf = 0;
    const tick = (now: number) => {
      const s = frames.sample(now);
      if (s && svg.current) {
        let target = FULL_VIEW;
        const c = cam.current;
        const p = c.on && c.id ? s.players.get(c.id) : undefined;
        if (p) {
          const w = CAM_WIDTH;
          const h = (w * FULL_VIEW[3]) / FULL_VIEW[2];
          const x = Math.min(Math.max(p.x - w / 2, FULL_VIEW[0]), FULL_VIEW[0] + FULL_VIEW[2] - w);
          const y = Math.min(Math.max(svgY(p.y) - h / 2, FULL_VIEW[1]), FULL_VIEW[1] + FULL_VIEW[3] - h);
          target = [x, y, w, h];
        }
        const k = c.reduce ? 1 : CAM_EASE;
        view.current = view.current.map((v, i) => v + (target[i]! - v) * k);
        svg.current.setAttribute("viewBox", view.current.map((v) => v.toFixed(2)).join(" "));
      }
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
        // keep the hover card next to its (moving) player
        const hid = hoverRef.current;
        const g = hid ? refs.current.get(hid)?.group : null;
        if (g && card.current && box.current) {
          const b = box.current.getBoundingClientRect();
          const r = g.getBoundingClientRect();
          const right = r.right - b.left + 10;
          const x = right + 208 > b.width ? r.left - b.left - 218 : right;
          const y = Math.min(Math.max(4, r.top - b.top - 20), b.height - card.current.offsetHeight - 4);
          card.current.style.transform = `translate(${x.toFixed(0)}px, ${y.toFixed(0)}px)`;
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
    <div ref={box} className="relative overflow-hidden rounded-lg bg-[var(--pitch-2)]">
      <svg
        ref={svg}
        viewBox={FULL_VIEW.join(" ")}
        className="block h-auto w-full select-none"
        role="img"
        aria-label={t("Live tactics board")}
      >
        <ArrowMarkers />
        <PitchSurface />
        {heat && focus && persona === "analyst" ? <HeatLayer playerId={focus} /> : null}
        <PitchMarkings />
        {Array.from({ length: TRAIL }, (_, i) => (
          <circle key={i} ref={(el) => (trail.current[i] = el)} r={0.35} fill="var(--on-pitch)" opacity={0} />
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
              role="button"
              tabIndex={0}
              aria-label={`${p.name}${focused ? " (followed)" : ""}`}
              className="cursor-pointer outline-none"
              onClick={() => (fan ? setPrefs({ player: focused ? null : id, followCam: true }) : openPanel(id))}
              onKeyDown={(e) => {
                if (e.key !== "Enter" && e.key !== " ") return;
                if (fan) setPrefs({ player: focused ? null : id, followCam: true });
                else openPanel(id);
              }}
              onPointerEnter={() => setHover(id)}
              onPointerLeave={() => setHover((h) => (h === id ? null : h))}
              onFocus={() => setHover(id)}
              onBlur={() => setHover((h) => (h === id ? null : h))}
              ref={(el) => {
                const r = refs.current.get(id) ?? { group: null, badge: null, badgeText: null };
                r.group = el;
                refs.current.set(id, r);
              }}
            >
              {focused ? <circle r={R * 2.4} fill="var(--on-pitch)" opacity={0.22} /> : null}
              {involved.has(id) ? (
                <circle r={R * 1.75} fill="none" stroke="var(--on-pitch)" strokeWidth={0.22} />
              ) : null}
              <PlayerDisc home={isHome} number={p.shirt_number} />
              <NameTag strong={tagged}>
                {surname(p.name)}
                {distanceBadges[id] ? ` · ${distanceBadges[id].label}` : ""}
              </NameTag>
              <g
                ref={(el) => {
                  const r = refs.current.get(id) ?? { group: null, badge: null, badgeText: null };
                  r.badge = el;
                  refs.current.set(id, r);
                }}
                transform={`translate(${R + 0.4} ${R + 0.2})`}
                style={{ opacity: 0, transition: "opacity 200ms var(--ease)" }}
              >
                <rect x={0} y={-0.95} width={5.6} height={1.7} rx={0.85} fill="var(--chrome)" />
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
                  fill="#fff"
                />
              </g>
            </g>
          );
        })}
        {/* above the players, so a sprint badge never hides a probability label */}
        <MomentLayer analysis={active} fan={persona === "fan"} />
        <ellipse ref={shadow} rx={0.6} ry={0.25} fill="var(--ink)" opacity={0.2} />
        <circle ref={ball} r={0.55} fill="#fff" stroke="var(--chrome)" strokeWidth={0.14} />
      </svg>
      {focus && persona === "analyst" ? (
        <button
          type="button"
          onClick={() => setHeat((v) => !v)}
          aria-pressed={heat}
          className={cn(
            "absolute left-4 top-4 inline-flex items-center gap-1.5 rounded-md border border-line bg-surface/90 px-2.5 py-1 text-xs shadow-sm backdrop-blur",
            heat ? "text-amber" : "text-muted hover:text-ink",
          )}
        >
          <Flame className="size-3.5" aria-hidden /> {t("Heat map")} · {players[focus]?.name.split(" ").pop()}
        </button>
      ) : null}
      {fan ? (
        <>
          <CamToggle />
          <PlayerCard />
          <MomentBanner />
        </>
      ) : null}
      {hover ? (
        <div ref={card} className="pointer-events-none absolute left-0 top-0 z-10" aria-live="polite">
          <HoverCard id={hover} />
        </div>
      ) : null}
      {onPitch.length === 0 ? (
        <div className="absolute inset-0 grid place-items-center text-sm text-white/80">{t("Waiting for the stream…")}</div>
      ) : null}
    </div>
  );
}
