import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Focus, Maximize2, RotateCcw, UserRound, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyMoment, MatchStats, PlayerStats } from "@/types/contracts";
import { api } from "@/lib/api";
import { commentary } from "@/lib/commentary";
import { sfx } from "@/lib/sfx";
import { km, surname } from "@/lib/format";
import { MOMENT_LABEL } from "@/lib/moments";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { useUi } from "@/state/ui";
import { replayMoment } from "../Scrubber";

/* Fan mode: everything here reads engine data already on the board, and writes only words,
   bars and the engine's own counts. No new numbers, no model calls. */

/** Follow-cam on/off, top-left of the pitch. */
export function CamToggle() {
  const followed = usePrefs((s) => s.player);
  const cam = usePrefs((s) => s.followCam);
  const set = usePrefs((s) => s.set);
  if (!followed) {
    return (
      <span className="pointer-events-none absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-chrome/80 px-3 py-1.5 text-xs text-white">
        <Focus className="size-3.5" aria-hidden /> Tap a player to follow them
      </span>
    );
  }
  return (
    <button
      type="button"
      onClick={() => set({ followCam: !cam })}
      aria-pressed={cam}
      className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-chrome/80 px-3 py-1.5 text-xs text-white hover:bg-chrome"
    >
      {cam ? <Maximize2 className="size-3.5" aria-hidden /> : <Focus className="size-3.5" aria-hidden />}
      {cam ? "Full pitch" : "Follow cam"}
    </button>
  );
}

/** The followed player on a small card: their counts and an energy bar (100 − fatigue). */
export function PlayerCard() {
  const id = usePrefs((s) => s.player);
  const set = usePrefs((s) => s.set);
  const p = useMatch((s) => (id ? s.players[id] : undefined));
  const w = useMatch((s) => (id ? s.workload[id] : undefined));
  const home = useMatch((s) => s.meta?.teams[0]?.team_id);
  const [stats, setStats] = useState<PlayerStats | null>(null);
  useEffect(() => {
    setStats(null);
    if (!id) return;
    let alive = true;
    const load = () =>
      api
        .playerStats(id)
        .then((s) => alive && setStats(s))
        .catch(() => undefined);
    void load();
    const t = setInterval(load, 10_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [id]);
  if (!id || !p) return null;
  const energy = Math.max(0, 100 - (w?.fatigue ?? 0));
  const isHome = p.team_id === home;
  const bits = stats
    ? [
        stats.goals ? `${stats.goals} goal${stats.goals > 1 ? "s" : ""}` : null,
        stats.shots ? `${stats.shots} shot${stats.shots > 1 ? "s" : ""}` : null,
        stats.aerial_duels ? `won ${stats.aerial_won} of ${stats.aerial_duels} headers` : null,
        stats.tackles_won ? `${stats.tackles_won} tackle${stats.tackles_won > 1 ? "s" : ""} won` : null,
        `${stats.passes_completed} passes`,
      ].filter(Boolean)
    : [];
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="absolute bottom-3 right-3 w-60 rounded-xl bg-surface/95 p-3 text-ink shadow-lg backdrop-blur"
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "num grid size-6 place-items-center rounded-full text-[11px] font-semibold",
            isHome ? "bg-riv text-white" : "bg-hil text-hil-ink",
          )}
        >
          {p.shirt_number}
        </span>
        <span className="min-w-0 flex-1 truncate text-sm font-semibold">{p.name}</span>
        <button
          type="button"
          onClick={() => set({ player: null })}
          className="rounded-md p-1 text-muted hover:bg-panel-2 hover:text-ink"
          aria-label="Stop following"
        >
          <X className="size-3.5" />
        </button>
      </div>
      <p className="mt-1 text-xs text-muted">Following · {w ? km(w.distance_m) : "–"}</p>
      <div className="mt-2 flex items-center gap-2 text-xs">
        <span className="text-muted">Energy</span>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel-2" aria-label={`Energy ${Math.round(energy)} of 100`}>
          <div
            className={cn("h-full rounded-full transition-[width] duration-700", energy > 60 ? "bg-green" : energy > 30 ? "bg-[#e0a800]" : "bg-red")}
            style={{ width: `${energy}%` }}
          />
        </div>
      </div>
      {bits.length ? <p className="mt-2 text-xs leading-relaxed">{bits.join(" · ")}</p> : null}
      <button
        type="button"
        onClick={() => useUi.getState().openPanel(id)}
        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-ink"
      >
        <UserRound className="size-3.5" aria-hidden /> Their big calls
      </button>
    </motion.div>
  );
}

const BANNER_TYPES = new Set(["goal", "big_chance", "aerial_duel", "recovery_run", "line_breaking_pass", "press_turnover"]);
const BANNER_MS = 6500;

/** A big moment drops a banner over the pitch, in the team's colour, with "Watch again". */
export function MomentBanner() {
  const reduce = useReducedMotion();
  const meta = useMatch((s) => s.meta);
  const [show, setShow] = useState<KeyMoment | null>(null);
  const shown = useRef(new Set<string>());

  // Fire when the clock plays across a moment (not on load or a seek), so replays get it too.
  useEffect(
    () =>
      useMatch.subscribe((s, prev) => {
        const dt = s.clockMs - prev.clockMs;
        if (dt <= 0 || dt > 5_000) return;
        const all = [...s.allMoments, ...Object.values(s.seen)];
        for (const m of all) {
          if (!BANNER_TYPES.has(m.type) || shown.current.has(m.moment_id)) continue;
          if (prev.clockMs < m.t_ms && s.clockMs >= m.t_ms) {
            shown.current.add(m.moment_id);
            setShow(m);
            (m.type === "goal" ? sfx.goal : sfx.moment)();
            setTimeout(() => shown.current.delete(m.moment_id), 20_000); // again on a later replay
          }
        }
      }),
    [],
  );
  useEffect(() => {
    if (!show) return;
    const t = setTimeout(() => setShow(null), BANNER_MS);
    return () => clearTimeout(t);
  }, [show]);

  const players = useMatch((s) => s.players);
  const home = meta?.teams[0]?.team_id;
  const isHome = show?.team_id === home;
  const scorer = show?.type === "goal" ? players[show.players[0] ?? ""] : undefined;
  const headline = scorer
    ? `${surname(scorer.name)} scores for ${meta?.teams.find((t) => t.team_id === show?.team_id)?.name ?? ""}`
    : show?.title;
  return (
    <AnimatePresence>
      {show ? (
        <motion.div
          key={show.moment_id}
          initial={reduce ? false : { opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -16 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className={cn(
            "absolute inset-x-3 top-3 z-10 flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg",
            show.type === "goal" ? (isHome ? "bg-riv text-white" : "bg-hil text-hil-ink") : "bg-chrome/90 text-white",
          )}
          role="status"
        >
          <span className="text-[11px] font-semibold uppercase tracking-wide opacity-80">
            {show.type === "goal" ? "Goal!" : MOMENT_LABEL[show.type]}
          </span>
          <span className="min-w-0 flex-1 truncate font-display text-base font-semibold">{headline}</span>
          <button
            type="button"
            onClick={() => void replayMoment(show)}
            className="inline-flex shrink-0 items-center gap-1 rounded-full bg-black/15 px-3 py-1 text-xs font-medium hover:bg-black/25"
          >
            <RotateCcw className="size-3.5" aria-hidden /> Watch again
          </button>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

interface Line {
  id: string;
  minute: number;
  text: string;
  big: boolean;
}

/** Live commentary under the pitch: engine events in plain words, newest first. */
export function CommentaryTicker() {
  const players = useMatch((s) => s.players);
  const teams = useMatch((s) => s.meta?.teams);
  const [lines, setLines] = useState<Line[]>([]);
  const seen = useRef(new Set<string>());

  useEffect(
    () =>
      useMatch.subscribe((s, prev) => {
        if (s.clockMs < prev.clockMs - 5_000) {
          seen.current.clear(); // a seek back: start the commentary again
          setLines([]);
        }
        if (s.events === prev.events) return;
        const fresh: Line[] = [];
        for (const e of s.events) {
          if (seen.current.has(e.event_id)) continue;
          seen.current.add(e.event_id);
          const text = commentary(e, s.players, s.meta?.teams);
          if (text) fresh.push({ id: e.event_id, minute: Math.floor(e.t_ms / 60_000) + 1, text, big: e.type === "goal" });
        }
        if (fresh.length) setLines((l) => [...fresh.reverse(), ...l].slice(0, 6));
      }),
    [players, teams],
  );

  return (
    <div className="chrome flex items-center gap-3 overflow-hidden rounded-lg bg-panel-2 px-3 py-2 text-sm" aria-live="polite" aria-label="Live commentary">
      <span className="shrink-0 text-[11px] font-semibold tracking-wide text-[#ffb547]">LIVE</span>
      {lines.length === 0 ? (
        <span className="text-muted">Commentary starts with the action…</span>
      ) : (
        <ol className="flex min-w-0 gap-4 whitespace-nowrap">
          {lines.map((l, i) => (
            <motion.li
              key={l.id}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: i === 0 ? 1 : 0.55, x: 0 }}
              className={cn(l.big && "font-semibold text-[#ffb547]")}
            >
              <span className="num mr-1 text-xs text-muted">{l.minute}'</span>
              {l.text}
            </motion.li>
          ))}
        </ol>
      )}
    </div>
  );
}

interface Sample {
  t: number;
  poss: number[]; // possession seconds per team
  threat: number[]; // xG + shots per team
}
const WINDOW_MS = 5 * 60_000;

function sample(s: MatchStats): Sample {
  return {
    t: s.t_ms,
    poss: s.teams.map((t) => t.possession * s.t_ms),
    threat: s.teams.map((t) => t.xg * 10 + t.shots),
  };
}

/** Who's on top over the last five minutes: the engine's possession and threat, as a bar. */
export function MomentumBar() {
  const stats = useMatch((s) => s.stats);
  const meta = useMatch((s) => s.meta);
  const history = useRef<Sample[]>([]);

  const share = useMemo(() => {
    if (!stats || stats.teams.length !== 2) return null;
    const now = sample(stats);
    const h = history.current;
    if (h.length && now.t < h[h.length - 1]!.t) h.length = 0; // seek back
    h.push(now);
    while (h.length > 2 && h[1]!.t <= now.t - WINDOW_MS) h.shift();
    const base = h[0]!;
    const dp = now.poss.map((v, i) => Math.max(0, v - base.poss[i]!));
    const dt = now.threat.map((v, i) => Math.max(0, v - base.threat[i]!));
    const pTot = dp[0]! + dp[1]!;
    const tTot = dt[0]! + dt[1]!;
    const poss = pTot > 0 ? dp[0]! / pTot : 0.5;
    return tTot > 0 ? 0.5 * poss + 0.5 * (dt[0]! / tTot) : poss;
  }, [stats]);

  if (share === null || !meta) return null;
  const [home, away] = meta.teams;
  const label =
    share > 0.6 ? `${home?.name} on top` : share < 0.4 ? `${away?.name} pressing` : "Even contest";
  return (
    <div className="chrome flex items-center gap-3 px-1 text-xs" aria-label={`Momentum: ${label}`}>
      <span className="text-muted">Momentum</span>
      <div className="flex h-2 flex-1 overflow-hidden rounded-full" aria-hidden>
        <motion.span className="bg-riv" animate={{ width: `${share * 100}%` }} transition={{ duration: 0.8 }} />
        <span className="flex-1 bg-hil" />
      </div>
      <span className={cn("w-36 text-right font-medium", share > 0.6 ? "text-white" : share < 0.4 ? "text-hil" : "text-muted")}>
        {label}
      </span>
    </div>
  );
}

/** Fan feed header: scorers, who's running on empty, and who you follow; tap to follow. */
export function PlayersToWatch() {
  const seen = useMatch((s) => s.seen);
  const workload = useMatch((s) => s.workload);
  const players = useMatch((s) => s.players);
  const onPitch = useMatch((s) => s.onPitch);
  const home = useMatch((s) => s.meta?.teams[0]?.team_id);
  const followed = usePrefs((s) => s.player);
  const set = usePrefs((s) => s.set);

  const chips = useMemo(() => {
    const out = new Map<string, string>();
    if (followed && players[followed]) out.set(followed, "following");
    for (const m of Object.values(seen).sort((a, b) => a.t_ms - b.t_ms)) {
      const id = m.players[0];
      if (m.type === "goal" && id && !out.has(id)) out.set(id, "scored");
    }
    const on = new Set(onPitch);
    Object.values(workload)
      .filter((w) => on.has(w.player_id) && w.fatigue >= 70 && !out.has(w.player_id))
      .sort((a, b) => b.fatigue - a.fatigue)
      .slice(0, 2)
      .forEach((w) => out.set(w.player_id, "tiring"));
    return [...out.entries()].filter(([id]) => players[id]);
  }, [seen, workload, players, onPitch, followed]);

  if (!chips.length) return null;
  return (
    <div className="rounded-2xl border border-line bg-surface p-3">
      <p className="text-xs font-medium text-muted">Players to watch</p>
      <ul className="mt-2 flex flex-wrap gap-1.5">
        {chips.map(([id, why]) => {
          const p = players[id]!;
          return (
            <li key={id}>
              <button
                type="button"
                onClick={() => set({ player: followed === id ? null : id, followCam: true })}
                aria-pressed={followed === id}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs",
                  p.team_id === home ? "bg-riv/10 text-riv-ink" : "bg-hil/20 text-hil-ink",
                  followed === id && "ring-2 ring-amber/50",
                )}
              >
                <span className="font-medium">{p.name.split(" ").pop()}</span>
                <span className="opacity-75">· {why}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
