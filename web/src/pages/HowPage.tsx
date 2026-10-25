import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Activity, Gauge, Languages, MessageSquareText, Pause, Play, Tv } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { PageHeader } from "@/components/Nav";
import { API_URL } from "@/lib/api";
import { href } from "@/lib/router";
import { msg, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";

interface TraceStep {
  step: string;
  source: string;
}

const EASE = [0.22, 1, 0.36, 1] as const;

function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.5, delay, ease: EASE }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  const t = useT();
  return (
    <div className="rounded-lg bg-panel-2 px-3 py-2.5">
      <p className="num text-lg font-medium leading-tight">{value}</p>
      <p className="mt-0.5 text-xs leading-snug text-muted">{t(label)}</p>
    </div>
  );
}

const FLOW = [
  { title: msg("Ingest"), icon: Activity, line: msg("A seeded simulator streams 22 players and the ball, 10 frames a second.") },
  { title: msg("Interpret"), icon: Gauge, line: msg("The engine turns every frame into workload, fatigue and odds.") },
  { title: msg("Explain"), icon: MessageSquareText, line: msg("Agents put the engine's numbers into words, and a guard checks every one.") },
  { title: msg("Render"), icon: Tv, line: msg("The board draws the options, the best one and the what-if ghost.") },
  { title: msg("Personalize"), icon: Languages, line: msg("Analyst or fan, your club, your player, your language.") },
] as const;

const PITCH = "repeating-linear-gradient(90deg,var(--pitch-1) 0 28px,var(--pitch-2) 28px 56px)";

/** A small looping pitch with players drifting: the simulator at work. */
function IngestScene({ reduce }: { reduce: boolean }) {
  const t = useT();
  const dots = [
    [18, 30, "bg-riv"], [30, 62, "bg-riv"], [46, 40, "bg-riv"], [60, 70, "bg-riv"],
    [52, 26, "bg-hil"], [70, 48, "bg-hil"], [82, 30, "bg-hil"], [38, 52, "bg-hil"],
  ] as const;
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="relative flex-1 overflow-hidden rounded-lg" style={{ background: PITCH }}>
        <div className="absolute inset-2 rounded-sm border border-white/60" />
        <div className="absolute inset-y-2 left-1/2 w-px bg-white/60" />
        {dots.map(([x, y, c], i) => (
          <motion.span
            key={i}
            className={cn("absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-white/70", c)}
            style={{ left: `${x}%`, top: `${y}%` }}
            animate={reduce ? undefined : { x: [0, (i % 3) * 8 - 6, 0], y: [0, (i % 2 ? 6 : -6), 0] }}
            transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: i * 0.1 }}
          />
        ))}
        <motion.span
          className="absolute size-2 rounded-full border border-chrome bg-white"
          style={{ top: "44%" }}
          animate={reduce ? { left: "50%" } : { left: ["22%", "48%", "72%", "48%", "22%"] }}
          transition={{ duration: 4.8, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>
      <p className="num text-xs text-muted">{t("10 Hz · 22 players + the ball")}</p>
    </div>
  );
}

/** Three engine gauges filling up. */
function InterpretScene({ reduce }: { reduce: boolean }) {
  const t = useT();
  const bars = [
    [msg("Workload"), 0.7, "bg-key"],
    [msg("Fatigue"), 0.55, "bg-amber"],
    [msg("Pass odds"), 0.82, "bg-green"],
  ] as const;
  return (
    <div className="flex h-full flex-col justify-center gap-4">
      {bars.map(([label, w, c], i) => (
        <div key={label}>
          <p className="mb-1.5 text-xs text-muted">{t(label)}</p>
          <div className="h-2.5 overflow-hidden rounded-full bg-surface">
            <motion.div
              className={cn("h-full rounded-full", c)}
              initial={{ width: reduce ? `${w * 100}%` : "0%" }}
              animate={{ width: `${w * 100}%` }}
              transition={{ duration: 1.1, delay: 0.15 + i * 0.2, ease: EASE }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/** A moment card writing itself, bullet by bullet. */
function ExplainScene({ reduce }: { reduce: boolean }) {
  const t = useT();
  const points = [
    [msg("a better finisher"), true],
    [msg("A pass to Venn was on"), true],
    [msg("Went for a shot instead"), false],
  ] as const;
  return (
    <div className="flex h-full flex-col gap-2 rounded-lg bg-surface p-3.5">
      <span className="self-start rounded-full bg-key px-2 py-0.5 text-[11px] font-semibold text-chrome">
        {t("Big chance")} · 58'
      </span>
      <p className="font-display text-base font-extrabold leading-tight">{t("Big chance missed by Reyes-Ward")}</p>
      <div className="flex flex-wrap gap-1.5">
        {points.map(([text, up], i) => (
          <motion.span
            key={text}
            initial={reduce ? false : { opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, delay: 0.4 + i * 0.35 }}
            className={cn(
              "rounded-full px-2 py-0.5 text-[11px] font-medium",
              up ? "bg-green/12 text-green" : "bg-red/12 text-red",
            )}
          >
            {up ? "▲" : "▼"} {t(text)}
          </motion.span>
        ))}
      </div>
      <p className="mt-auto text-[11px] text-muted">{t("Every number checked against the engine")}</p>
    </div>
  );
}

/** Option arrows drawing onto the pitch, with the what-if ghost. */
function RenderScene({ reduce }: { reduce: boolean }) {
  const draw = (delay: number) =>
    reduce
      ? { initial: false as const }
      : { initial: { pathLength: 0 }, animate: { pathLength: 1 }, transition: { duration: 0.8, delay, ease: EASE } };
  return (
    <div className="relative h-full overflow-hidden rounded-lg" style={{ background: PITCH }}>
      <svg viewBox="0 0 200 120" className="absolute inset-0 size-full" aria-hidden>
        <rect x="4" y="4" width="192" height="112" fill="none" stroke="rgba(255,255,255,.6)" />
        <rect x="160" y="34" width="36" height="52" fill="none" stroke="rgba(255,255,255,.6)" />
        <motion.path d="M70 66 C 110 40, 140 40, 178 58" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" {...draw(0.2)} />
        <motion.path d="M70 66 L 120 92" fill="none" stroke="rgba(255,255,255,.7)" strokeWidth="1.6" strokeDasharray="4 4" {...draw(0.6)} />
        <circle cx="70" cy="66" r="6" fill="var(--riv)" stroke="var(--riv-rim)" strokeWidth="1.5" />
        <circle cx="150" cy="70" r="6" fill="var(--hil)" stroke="var(--hil-rim)" strokeWidth="1.5" />
        <motion.circle
          cx="96" cy="50" r="7" fill="none" stroke="#fff" strokeWidth="1.5" strokeDasharray="3 3"
          initial={reduce ? false : { opacity: 0, scale: 0.6 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 1.1 }}
        />
      </svg>
    </div>
  );
}

/** The same moment flipping between personas and languages. */
function PersonalizeScene({ reduce }: { reduce: boolean }) {
  const t = useT();
  const langs = ["EN", "ES", "FR", "PT", "DE", "हि"];
  const [k, setK] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setK((v) => v + 1), 700);
    return () => clearInterval(id);
  }, [reduce]);
  const fan = k % 4 >= 2;
  return (
    <div className="flex h-full flex-col gap-3">
      <div className="flex gap-1 self-start rounded-full bg-surface p-1 text-xs font-semibold">
        <span className={cn("rounded-full px-3 py-1 transition-colors", !fan ? "bg-chrome text-white" : "text-muted")}>{t("Analyst")}</span>
        <span className={cn("rounded-full px-3 py-1 transition-colors", fan ? "bg-chrome text-white" : "text-muted")}>{t("Fan")}</span>
      </div>
      <div className="flex-1 rounded-lg bg-surface p-3 text-sm leading-snug">
        {fan
          ? t("Felix Dunmore would have been much more likely to win that header.")
          : t("Pell had a {a} chance; a fresh aerial centre-back would have had {b}: +32 cm reach, +42 aerial.", { a: "4%", b: "46%" })}
      </div>
      <div className="flex gap-1.5">
        {langs.map((l, i) => (
          <span
            key={l}
            className={cn(
              "rounded-md px-2 py-0.5 text-[11px] font-semibold transition-colors",
              i === k % langs.length ? "bg-key text-chrome" : "bg-surface text-muted",
            )}
          >
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

const SCENES = [IngestScene, InterpretScene, ExplainScene, RenderScene, PersonalizeScene];

/**
 * The system as a short looping film: a signal travels the five stages and each one plays its
 * scene. Hover pauses it, the stage buttons jump to a stage, and reduced motion shows stills.
 */
function SystemFlow() {
  const t = useT();
  const reduce = useReducedMotion() ?? false;
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const playing = !paused && !reduce;
  useEffect(() => {
    if (!playing) return;
    const id = setTimeout(() => setI((v) => (v + 1) % FLOW.length), 3200);
    return () => clearTimeout(id);
  }, [i, playing]);
  const Scene = SCENES[i]!;
  return (
    <div
      className="chrome rounded-3xl bg-chrome p-5 shadow-lg"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="relative">
        <div className="absolute inset-x-[10%] top-5 h-0.5 rounded-full bg-line-2" />
        <motion.div
          className="absolute left-[10%] top-5 h-0.5 rounded-full bg-key"
          animate={{ width: `${(i / (FLOW.length - 1)) * 80}%` }}
          transition={{ duration: reduce ? 0 : 0.6, ease: EASE }}
        />
        <ol className="relative grid grid-cols-5">
          {FLOW.map((s, n) => {
            const Icon = s.icon;
            return (
              <li key={s.title} className="flex flex-col items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => setI(n)}
                  aria-current={n === i ? "step" : undefined}
                  aria-label={t(s.title)}
                  className={cn(
                    "grid size-10 place-items-center rounded-full transition-colors duration-300",
                    n <= i ? "bg-key text-chrome" : "bg-surface text-muted hover:text-ink",
                    n === i && "ring-4 ring-key/25",
                  )}
                >
                  <Icon className="size-4" aria-hidden />
                </button>
                <span className={cn("text-center text-[11px] font-medium", n === i ? "text-ink" : "text-muted")}>{t(s.title)}</span>
              </li>
            );
          })}
        </ol>
      </div>
      <div className="mt-4 h-[210px] rounded-2xl bg-panel-2 p-4">
        <AnimatePresence mode="wait">
          <motion.div
            key={i}
            className="h-full"
            initial={reduce ? false : { opacity: 0, x: 18 }}
            animate={{ opacity: 1, x: 0 }}
            exit={reduce ? undefined : { opacity: 0, x: -18 }}
            transition={{ duration: 0.35, ease: EASE }}
          >
            <Scene reduce={reduce} />
          </motion.div>
        </AnimatePresence>
      </div>
      <div className="mt-3 flex items-start gap-3">
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          aria-label={paused ? t("Play") : t("Pause")}
          className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-full bg-surface text-ink"
        >
          {paused ? <Play className="size-3.5" aria-hidden /> : <Pause className="size-3.5" aria-hidden />}
        </button>
        <p className="min-h-[2.5rem] text-sm leading-snug text-ink">
          <span className="num mr-2 text-key">0{i + 1}</span>
          {t(FLOW[i]!.line)}
        </p>
      </div>
    </div>
  );
}

const ROUTER: [string, string][] = [
  [msg("Every frame or event"), msg("Engine only, no model")],
  [msg("Key moment"), msg("Moment → What-if → Narrator")],
  [msg("Fatigue over 80"), msg("What-if (fresh sub) → Narrator")],
  [msg("Language change"), msg("Translator only")],
  [msg("Half-time, full-time"), msg("Interpreter → Recap → Decisions")],
  [msg("A viewer asks the copilot"), msg("Copilot agent with engine tools")],
];

/** The agent layout: router in, five agents, MCP tools onto the engine, grounding guard out. */
function AgentDiagram() {
  const t = useT();
  const box = (x: number, y: number, w: number, label: string, sub: string, dark = false) => (
    <g transform={`translate(${x} ${y})`}>
      <rect width={w} height={52} rx={12} fill={dark ? "var(--chrome)" : "var(--surface)"} stroke="var(--line-2)" />
      <text x={w / 2} y={22} textAnchor="middle" fontSize={13} fontWeight={600} fill={dark ? "#ffffff" : "var(--ink)"}>
        {t(label)}
      </text>
      <text x={w / 2} y={39} textAnchor="middle" fontSize={10.5} fill={dark ? "#cdbbd6" : "var(--muted)"}>
        {t(sub)}
      </text>
    </g>
  );
  const line = (x1: number, y1: number, x2: number, y2: number, dashed = false) => (
    <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--line-2)" strokeWidth={1.5} strokeDasharray={dashed ? "4 4" : undefined} markerEnd="url(#how-arrow)" />
  );
  return (
    <svg viewBox="0 0 640 330" className="h-auto w-full" role="img" aria-label={t("Agent architecture")}>
      <defs>
        <marker id="how-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
          <path d="M0 0L10 5L0 10z" fill="var(--muted-2)" />
        </marker>
      </defs>
      {box(10, 20, 150, msg("Stream + engine"), msg("every number"))}
      {box(245, 20, 150, msg("Rules router"), msg("decision table"), true)}
      {box(480, 20, 150, msg("Board"), msg("cards · overlays"))}
      {line(160, 46, 243, 46)}
      {box(20, 130, 110, msg("Moment"), msg("frames it"))}
      {box(145, 130, 110, msg("What-if"), msg("picks a swap"))}
      {box(270, 130, 110, msg("Narrator"), msg("mini · nano"))}
      {box(395, 130, 110, msg("Interpreter"), msg("match state"))}
      {box(520, 130, 110, msg("Recap"), msg("turning points"))}
      {line(320, 72, 75, 128)}
      {line(320, 72, 200, 128)}
      {line(320, 72, 325, 128)}
      {line(320, 72, 450, 128)}
      {line(320, 72, 575, 128)}
      {box(125, 250, 150, msg("MCP tools"), msg("6 engine tools"))}
      {line(200, 182, 200, 248)}
      {line(125, 276, 85, 74, true)}
      {box(330, 250, 170, msg("Grounding guard"), msg("numbers ⊆ engine"), true)}
      {line(325, 182, 400, 248)}
      {line(500, 276, 555, 74)}
      {box(520, 250, 110, msg("Translator"), msg("Azure AI"))}
    </svg>
  );
}

/** One stage of the pipeline as a compact card: number, title, what happens, and live figures. */
function StageCard({
  n,
  icon,
  title,
  lead,
  children,
  className,
}: {
  n: number;
  icon: ReactNode;
  title: string;
  lead: string;
  children: ReactNode;
  className?: string;
}) {
  const t = useT();
  return (
    <Reveal className={cn("rounded-2xl border border-line bg-surface p-5", className)}>
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-lg bg-chrome text-white">{icon}</span>
        <h2 className="font-display text-xl font-extrabold tracking-tight">
          <span className="num mr-2 text-sm text-key">0{n}</span>
          {t(title)}
        </h2>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-ink/80">{t(lead)}</p>
      <div className="mt-4">{children}</div>
    </Reveal>
  );
}

export function HowPage() {
  const t = useT();
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
      <main className="mx-auto max-w-[1200px] px-4 pb-16 lg:px-6">
        <section className="grid items-center gap-8 py-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)] lg:gap-12 lg:py-14">
          <Reveal>
            <p className="text-sm font-medium uppercase tracking-wide text-key">{t("How it works")}</p>
            <h1 className="mt-3 font-display text-4xl font-extrabold tracking-tight lg:text-5xl">
              {t("One pipeline, five stages, every number from the engine.")}
            </h1>
            <p className="mt-4 max-w-xl text-base leading-relaxed text-ink/80">
              {t("A fully synthetic match streams in, a transparent probability engine interprets it, agents explain the key moments in words, the board renders them, and every fan gets their own view.")}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <a href={href("live")} className="rounded-md bg-chrome px-4 py-2 text-sm font-medium text-white">
                {t("Watch it live")}
              </a>
              <a href={href("recap")} className="rounded-md border border-line bg-surface px-4 py-2 text-sm font-medium">
                {t("Read the recap")}
              </a>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <SystemFlow />
          </Reveal>
        </section>

        <div className="grid gap-4 lg:grid-cols-2">
          <StageCard
            n={1}
            icon={<Activity className="size-4" />}
            title={msg("Ingest")}
            lead={msg("A seeded simulator plays a believable 90 minutes: formations that breathe with the ball, forward runs, presses, duels and five scripted turning points. It streams at 10 frames a second.")}
          >
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
              <Stat value={frames.toLocaleString("en-GB")} label={msg("tracking frames (10 Hz)")} />
              <Stat value="22" label={msg("players + the ball, every frame")} />
              <Stat value="1× – 8×" label={msg("replay speed, pause and seek")} />
              <Stat value="100%" label={msg("synthetic: no real clubs or players")} />
            </div>
          </StageCard>

          <StageCard
            n={2}
            icon={<Gauge className="size-4" />}
            title={msg("Interpret")}
            lead={msg("Every frame updates workload, fatigue, team stats and a five-minute intensity index. Fatigue feeds straight back into the probabilities: tired legs are slower, react later and jump lower.")}
          >
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
              <Stat value={h ? `${Math.round(h.possession * 100)}–${Math.round((a?.possession ?? 0) * 100)}` : "–"} label={msg("possession so far (%)")} />
              <Stat value={h ? `${h.passes + (a?.passes ?? 0)}` : "–"} label={msg("passes recounted from events")} />
              <Stat value="< 1%" label={msg("workload error against raw tracking")} />
              <Stat value="0.012" label={msg("pass-probability calibration error")} />
            </div>
          </StageCard>

          <StageCard
            n={3}
            icon={<MessageSquareText className="size-4" />}
            title={msg("Explain")}
            lead={msg("A detector flags the moments worth explaining. The engine maps the options and runs a what-if: what if a fresh specialist had been there? Then the agents put it into words, and every number they write is checked against the engine.")}
            className="lg:col-span-2"
          >
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)] lg:items-center">
              <div className="rounded-xl bg-panel-2 p-4">
                <AgentDiagram />
                <p className="mt-2 text-xs text-muted">
                  {t("Agents never pass numbers to each other: the What-if agent changes the engine through MCP, the Narrator reads the result.")}
                </p>
              </div>
              <table className="w-full text-sm">
                <tbody className="divide-y divide-line">
                  {ROUTER.map(([trig, run]) => (
                    <tr key={trig}>
                      <td className="py-2 pr-3 text-muted">{t(trig)}</td>
                      <td className="py-2 text-right font-medium">{t(run)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </StageCard>

          <StageCard
            n={4}
            icon={<Tv className="size-4" />}
            title={msg("Render")}
            lead={msg("The board glides between frames at 60 fps. Key moments arrive as cards, option arrows and what-if ghosts, and every card exports as time-coded JSON for a broadcast graphics engine.")}
          >
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-2">
              <Stat value={String(allMoments.length)} label={msg("key moments detected in this match")} />
              <Stat value={String(Object.keys(overlays).length)} label={msg("cards rendered so far")} />
              <Stat value={narrated.length ? `${byAgents}/${narrated.length}` : "–"} label={msg("texts written by agents (rest: engine templates)")} />
              <Stat value="0" label={msg("numbers invented by a model")} />
            </div>
          </StageCard>

          <StageCard
            n={5}
            icon={<Languages className="size-4" />}
            title={msg("Personalize")}
            lead={msg("The same moment becomes an analyst card with ranges and drivers or a one-line fan story. Follow a club or a player and their moments come first. Switch language and the whole board follows: cards are translated without a new model call, and the copilot answers in it.")}
          >
            <div className="grid gap-2 sm:grid-cols-2">
              <div className="rounded-lg bg-panel-2 p-3">
                <p className="text-xs text-muted">{t("Analyst")}</p>
                <p className="mt-1 text-sm">
                  {t("Pell had a {a} chance; a fresh aerial centre-back would have had {b}: +32 cm reach, +42 aerial.", { a: "4%", b: "46%" })}
                </p>
              </div>
              <div className="rounded-lg bg-panel-2 p-3">
                <p className="text-xs text-muted">{t("Fan")}</p>
                <p className="mt-1 text-sm font-medium leading-snug">
                  {t("Felix Dunmore would have been much more likely to win that header.")}
                </p>
              </div>
            </div>
          </StageCard>
        </div>
      </main>
    </div>
  );
}
