import { motion } from "framer-motion";
import { Activity, Gauge, Languages, Sparkles, Tv } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/Nav";
import { API_URL } from "@/lib/api";
import { href } from "@/lib/router";
import { useLenis } from "@/lib/useLenis";
import { useMatch } from "@/state/match";

interface TraceStep {
  step: string;
  source: string;
}

function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.7, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
      <p className="num text-2xl font-medium">{value}</p>
      <p className="mt-1 text-xs text-muted">{label}</p>
    </div>
  );
}

function Stage({
  n,
  icon,
  title,
  lead,
  children,
}: {
  n: number;
  icon: ReactNode;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <section data-snap className="flex min-h-[85vh] items-center py-16">
      <div className="grid w-full gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] lg:gap-16">
        <Reveal>
          <p className="num text-sm text-amber">0{n}</p>
          <h2 className="mt-2 flex items-center gap-3 font-display text-3xl font-semibold tracking-tight lg:text-4xl">
            <span className="grid size-10 place-items-center rounded-md bg-ink text-surface">{icon}</span>
            {title}
          </h2>
          <p className="mt-4 max-w-lg text-lg leading-relaxed text-ink/80">{lead}</p>
        </Reveal>
        <Reveal delay={0.12}>{children}</Reveal>
      </div>
    </section>
  );
}

const ROUTER: [string, string][] = [
  ["Every frame or event", "Engine only, no model"],
  ["Key moment", "Moment → What-if → Narrator"],
  ["Fatigue over 80", "What-if (fresh sub) → Narrator"],
  ["Language change", "Translator only"],
  ["Half-time, full-time", "Interpreter → Recap"],
];

/** The agent layout: router in, five agents, MCP tools onto the engine, grounding guard out. */
function AgentDiagram() {
  const box = (x: number, y: number, w: number, label: string, sub: string, dark = false) => (
    <g transform={`translate(${x} ${y})`}>
      <rect width={w} height={52} rx={12} fill={dark ? "var(--ink)" : "var(--surface)"} stroke="var(--line-2)" />
      <text x={w / 2} y={22} textAnchor="middle" fontSize={13} fontWeight={600} fill={dark ? "var(--surface)" : "var(--ink)"}>
        {label}
      </text>
      <text x={w / 2} y={39} textAnchor="middle" fontSize={10.5} fill={dark ? "var(--muted-2)" : "var(--muted)"}>
        {sub}
      </text>
    </g>
  );
  const line = (x1: number, y1: number, x2: number, y2: number, dashed = false) => (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-2)" strokeWidth={1.5} strokeDasharray={dashed ? "4 4" : undefined} markerEnd="url(#how-arrow)" />
  );
  return (
    <svg viewBox="0 0 640 360" className="h-auto w-full" role="img" aria-label="Agent architecture">
      <defs>
        <marker id="how-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0L10 5L0 10z" fill="var(--muted-2)" />
        </marker>
      </defs>
      {box(10, 20, 150, "Stream + engine", "every number")}
      {box(245, 20, 150, "Rules router", "decision table", true)}
      {box(480, 20, 150, "Board", "cards · overlays")}
      {line(160, 46, 243, 46)}
      {box(20, 130, 110, "Moment", "frames it")}
      {box(145, 130, 110, "What-if", "picks a swap")}
      {box(270, 130, 110, "Narrator", "mini · nano")}
      {box(395, 130, 110, "Interpreter", "match state")}
      {box(520, 130, 110, "Recap", "turning points")}
      {line(320, 72, 75, 128)}
      {line(320, 72, 200, 128)}
      {line(320, 72, 325, 128)}
      {line(320, 72, 450, 128)}
      {line(320, 72, 575, 128)}
      {box(125, 250, 150, "MCP tools", "6 engine tools")}
      {line(200, 182, 200, 248)}
      {line(125, 276, 85, 74, true)}
      {box(330, 250, 170, "Grounding guard", "numbers ⊆ engine", true)}
      {line(325, 182, 400, 248)}
      {line(500, 276, 555, 74)}
      {box(520, 250, 110, "Translator", "Azure AI")}
      <text x={10} y={340} fontSize={10.5} fill="var(--muted)">
        Agents never pass numbers to each other: the What-if agent changes the engine through MCP, the Narrator reads the result.
      </text>
    </svg>
  );
}

export function HowPage() {
  useLenis();
  const status = useMatch((s) => s.status);
  const stats = useMatch((s) => s.stats);
  const allMoments = useMatch((s) => s.allMoments);
  const overlays = useMatch((s) => s.overlays);
  const [traces, setTraces] = useState<{ steps: TraceStep[] }[]>([]);
  useEffect(() => {
    fetch(`${API_URL}/agents/traces`)
      .then((r) => r.json())
      .then(setTraces)
      .catch(() => undefined);
  }, []);

  const frames = status ? Math.round(status.duration_ms / 100) : 54_000;
  const narrated = traces.flatMap((t) => t.steps).filter((s) => s.step === "narrator" || s.step === "recap");
  const byAgents = narrated.filter((s) => s.source === "agent" || s.source === "cache").length;
  const [h, a] = stats?.teams ?? [];

  return (
    <div className="min-h-dvh bg-bg">
      <PageHeader route="how" />
      <main className="mx-auto max-w-[1200px] px-4 pb-24 lg:px-6">
        <section data-snap className="flex min-h-[80vh] flex-col justify-center py-16">
          <Reveal>
            <p className="text-sm font-medium uppercase tracking-wide text-amber">How it works</p>
            <h1 className="mt-3 max-w-3xl font-display text-4xl font-semibold tracking-tight lg:text-6xl">
              One pipeline, five stages, every number from the engine.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-relaxed text-ink/80">
              A fully synthetic match streams in, a transparent probability engine interprets it, agents explain the key
              moments in words, the board renders them, and every fan gets their own view.
            </p>
            <ol className="mt-10 flex flex-wrap items-center gap-2 text-sm">
              {["Ingest", "Interpret", "Explain", "Render", "Personalize"].map((s, i) => (
                <li key={s} className="flex items-center gap-2">
                  <span className="rounded-full border border-line bg-surface px-3 py-1.5 shadow-sm">
                    <span className="num mr-1.5 text-amber">{i + 1}</span>
                    {s}
                  </span>
                  {i < 4 ? <span className="text-muted-2">→</span> : null}
                </li>
              ))}
            </ol>
          </Reveal>
        </section>

        <Stage
          n={1}
          icon={<Activity className="size-5" />}
          title="Ingest"
          lead="A seeded simulator plays a believable 90 minutes: formations that breathe with the ball, forward runs, presses, duels and five scripted turning points. It streams at 10 frames a second."
        >
          <div className="grid grid-cols-2 gap-3">
            <Stat value={frames.toLocaleString("en-GB")} label="tracking frames (10 Hz)" />
            <Stat value="22" label="players + the ball, every frame" />
            <Stat value="1× – 8×" label="replay speed, pause and seek" />
            <Stat value="100%" label="synthetic: no real clubs or players" />
          </div>
        </Stage>

        <Stage
          n={2}
          icon={<Gauge className="size-5" />}
          title="Interpret"
          lead="Every frame updates workload, fatigue, team stats and a five-minute intensity index. Fatigue feeds straight back into the probabilities: tired legs are slower, react later and jump lower."
        >
          <div className="grid grid-cols-2 gap-3">
            <Stat value={h ? `${Math.round(h.possession * 100)}–${Math.round((a?.possession ?? 0) * 100)}` : "–"} label="possession so far (%)" />
            <Stat value={h ? `${h.passes + (a?.passes ?? 0)}` : "–"} label="passes recounted from events" />
            <Stat value="< 1%" label="workload error against raw tracking" />
            <Stat value="0.02" label="pass-probability calibration error" />
          </div>
        </Stage>

        <Stage
          n={3}
          icon={<Sparkles className="size-5" />}
          title="Explain"
          lead="A detector flags the moments worth explaining. The engine maps the options and runs a what-if: what if a fresh specialist had been there? Then the agents put it into words, and every number they write is checked against the engine."
        >
          <div className="rounded-xl border border-line bg-surface p-5 shadow-md">
            <AgentDiagram />
          </div>
          <table className="mt-4 w-full text-sm">
            <tbody className="divide-y divide-line">
              {ROUTER.map(([t, r]) => (
                <tr key={t}>
                  <td className="py-2 text-muted">{t}</td>
                  <td className="py-2 text-right font-medium">{r}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Stage>

        <Stage
          n={4}
          icon={<Tv className="size-5" />}
          title="Render"
          lead="The board glides between frames at 60 fps. Key moments arrive as cards, option arrows and what-if ghosts, and every card exports as time-coded JSON for a broadcast graphics engine."
        >
          <div className="grid grid-cols-2 gap-3">
            <Stat value={String(allMoments.length)} label="key moments detected in this match" />
            <Stat value={String(Object.keys(overlays).length)} label="cards rendered so far" />
            <Stat value={narrated.length ? `${byAgents}/${narrated.length}` : "–"} label="texts written by agents (rest: engine templates)" />
            <Stat value="0" label="numbers invented by a model" />
          </div>
        </Stage>

        <Stage
          n={5}
          icon={<Languages className="size-5" />}
          title="Personalize"
          lead="The same moment becomes an analyst card with ranges and drivers or a one-line fan story. Follow a club or a player and their moments come first. Switch language and the card is translated without a new model call."
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
              <p className="text-xs text-muted">Analyst</p>
              <p className="mt-2 text-sm">
                Pell had a <span className="num">4%</span> chance (range <span className="num">4–4%</span>); a fresh aerial
                centre-back would have had <span className="num text-green">43%</span>: +31 cm reach, +42 aerial.
              </p>
            </div>
            <div className="rounded-lg border border-line bg-surface p-4 shadow-sm">
              <p className="text-xs text-muted">Fan</p>
              <p className="mt-2 text-lg leading-snug">
                Felix Dunmore would have been <strong className="text-green">much more likely</strong> to win that header.
              </p>
            </div>
          </div>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href={href("live")} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface">
              Watch it live
            </a>
            <a href={href("recap")} className="rounded-md border border-line bg-surface px-4 py-2 text-sm font-medium">
              Read the recap
            </a>
          </div>
        </Stage>
      </main>
    </div>
  );
}
