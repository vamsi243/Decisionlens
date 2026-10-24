import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, GitCompareArrows, Radar, Route as RouteIcon, ScanSearch } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { StaticBoard } from "@/components/board/StaticBoard";
import { PageHeader } from "@/components/Nav";
import { api } from "@/lib/api";
import { minute, pct } from "@/lib/format";
import { href } from "@/lib/router";
import { useMatch } from "@/state/match";
import type { MomentAnalysis, TrackingFrame } from "@/types/contracts";

const HOLD_FRAMES = 35; // ~3.5 s on the option map before the clip loops

function Reveal({ children, delay = 0 }: { children: ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** The 86' aerial duel on a loop, like a GIF: real frames from the stream, then the what-if. */
function HeroClip() {
  const moments = useMatch((s) => s.allMoments);
  const players = useMatch((s) => s.players);
  const home = useMatch((s) => s.meta?.teams[0]?.team_id);
  const reduce = useReducedMotion();
  const moment = useMemo(
    () => moments.find((m) => m.type === "aerial_duel") ?? moments.find((m) => m.type !== "fatigue_alert"),
    [moments],
  );
  const [clip, setClip] = useState<TrackingFrame[]>([]);
  const [analysis, setAnalysis] = useState<MomentAnalysis | null>(null);
  const [i, setI] = useState(0);

  useEffect(() => {
    if (!moment) return;
    let alive = true;
    void api.frames(moment.moment_id, 1).then((f) => alive && setClip(f)).catch(() => undefined);
    void api.analysis(moment.moment_id).then((a) => alive && setAnalysis(a)).catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [moment]);

  useEffect(() => {
    if (!clip.length || reduce) return;
    const t = setInterval(() => setI((v) => (v + 1) % (clip.length + HOLD_FRAMES)), 100);
    return () => clearInterval(t);
  }, [clip.length, reduce]);

  const at = reduce ? clip.length - 1 : Math.min(i, clip.length - 1);
  const frame = clip[at] ?? null;
  const done = clip.length > 0 && at >= clip.length - 1;
  const w = analysis?.what_if;

  return (
    <div className="relative">
      <div className="rounded-3xl bg-chrome p-3 shadow-lg">
        <StaticBoard
          frame={frame}
          players={players}
          homeTeam={home}
          analysis={analysis}
          showLayer={done}
          highlight={moment?.players ?? []}
          label="A key moment replaying on a loop"
        />
        <div className="flex items-center justify-between px-2 pt-3 text-xs text-white/70">
          <span className="inline-flex items-center gap-2">
            <span className="size-1.5 animate-pulse rounded-full bg-[#ff6b62]" aria-hidden />
            Replay · {moment ? minute(moment.t_ms) : "–"} {moment?.title ?? "Loading the match…"}
          </span>
          <span className="num">{clip.length ? `${Math.min(100, Math.round((at / (clip.length - 1)) * 100))}%` : ""}</span>
        </div>
      </div>
      {w ? (
        <motion.div
          initial={false}
          animate={{ opacity: done ? 1 : 0, y: done ? 0 : 12 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="absolute -bottom-6 left-4 w-[260px] rounded-xl border border-l-4 border-line border-l-riv bg-surface p-4 shadow-lg sm:-left-6"
          aria-hidden={!done}
        >
          <p className="text-xs text-muted">What if?</p>
          <p className="mt-1 flex items-baseline gap-2">
            <span className="num text-2xl font-medium">{pct(w.actual.p_success)}</span>
            <ArrowRight className="size-4 self-center text-muted" aria-hidden />
            <span className="num text-2xl font-medium text-green">{pct(w.counterfactual.p_success)}</span>
          </p>
          <p className="mt-1 text-xs text-muted">with {w.counterfactual.profile.label}</p>
        </motion.div>
      ) : null}
    </div>
  );
}

function Feature({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <div className="h-full rounded-2xl border border-line bg-surface p-6 shadow-sm">
      <span className="grid size-11 place-items-center rounded-xl bg-chrome text-white">{icon}</span>
      <h3 className="mt-5 font-display text-lg font-semibold tracking-tight">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-ink/75">{children}</p>
    </div>
  );
}

export function HomePage() {
  const moments = useMatch((s) => s.allMoments);
  const meta = useMatch((s) => s.meta);
  const [home, away] = meta?.teams ?? [];
  const keyMoments = moments.filter((m) => m.type !== "fatigue_alert").length;

  return (
    <div className="min-h-dvh bg-bg">
      <PageHeader route="home" />
      <main>
        {/* hero */}
        <section className="mx-auto grid max-w-[1280px] items-center gap-14 px-4 pb-24 pt-16 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] lg:gap-16 lg:px-8 lg:pt-24">
          <Reveal>
            <p className="text-sm font-medium uppercase tracking-wide text-amber">Live football, explained</p>
            <h1 className="mt-4 font-display text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
              See every decision, not just the result.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink/75">
              Decision Lens watches a match as it happens, picks out the moments that mattered and shows what each
              option was worth, and what a fresh pair of legs would have changed.
            </p>
            <div className="mt-9 flex flex-wrap gap-3">
              <a
                href={href("live")}
                className="inline-flex items-center gap-2 rounded-lg bg-chrome px-5 py-3 text-sm font-medium text-white transition-colors hover:bg-chrome/85"
              >
                Watch the live match <ArrowRight className="size-4" aria-hidden />
              </a>
              <a
                href={href("how")}
                className="rounded-lg border border-line-2 bg-surface px-5 py-3 text-sm font-medium transition-colors hover:bg-panel-2"
              >
                How it works
              </a>
            </div>
            <dl className="mt-12 grid max-w-md grid-cols-3 gap-6 border-t border-line pt-6">
              {[
                ["10 Hz", "player tracking"],
                [keyMoments ? String(keyMoments) : "–", "key moments explained"],
                ["0", "numbers from the model"],
              ].map(([v, l]) => (
                <div key={l}>
                  <dt className="sr-only">{l}</dt>
                  <dd className="num text-2xl font-medium">{v}</dd>
                  <dd className="mt-1 text-xs leading-snug text-muted">{l}</dd>
                </div>
              ))}
            </dl>
          </Reveal>
          <Reveal delay={0.1}>
            <HeroClip />
          </Reveal>
        </section>

        {/* what it does */}
        <section className="border-y border-line bg-surface/60 py-24">
          <div className="mx-auto max-w-[1280px] px-4 lg:px-8">
            <Reveal>
              <p className="text-sm font-medium uppercase tracking-wide text-amber">What you get</p>
              <h2 className="mt-3 max-w-2xl font-display text-3xl font-semibold tracking-tight lg:text-4xl">
                A tactics board that explains itself.
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-6 md:grid-cols-3">
              <Reveal>
                <Feature icon={<ScanSearch className="size-5" />} title="Spots the moments that matter">
                  Big chances, line-breaking passes, presses, recovery runs and aerial duels are picked out of the tracking
                  data the moment they happen.
                </Feature>
              </Reveal>
              <Reveal delay={0.08}>
                <Feature icon={<Radar className="size-5" />} title="Weighs every option">
                  Each option is drawn on the pitch with its chance of success, so you can see whether the player picked
                  the best one.
                </Feature>
              </Reveal>
              <Reveal delay={0.16}>
                <Feature icon={<GitCompareArrows className="size-5" />} title="Asks what if">
                  Swap a tired player for a fresh substitute and see how much more likely the moment would have been,
                  with the reasons in green and red.
                </Feature>
              </Reveal>
            </div>
          </div>
        </section>

        {/* two audiences */}
        <section className="mx-auto max-w-[1280px] px-4 py-24 lg:px-8">
          <div className="grid items-center gap-12 lg:grid-cols-2 lg:gap-16">
            <Reveal>
              <p className="text-sm font-medium uppercase tracking-wide text-amber">Two ways to watch</p>
              <h2 className="mt-3 font-display text-3xl font-semibold tracking-tight lg:text-4xl">
                Numbers for analysts, plain words for fans.
              </h2>
              <p className="mt-5 max-w-lg text-lg leading-relaxed text-ink/75">
                Flip one switch. Analysts get probabilities, ranges and drivers; fans get the same moment as one line they
                can share. Every number comes from the engine; the language model only puts it into words.
              </p>
            </Reveal>
            <Reveal delay={0.1}>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-2xl border border-l-4 border-line border-l-riv bg-surface p-5 shadow-sm">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">Analyst</p>
                  <ul className="mt-3 space-y-1.5 text-sm">
                    <li className="rounded-md bg-green/10 px-2 py-1 text-green">▲ more reach</li>
                    <li className="rounded-md bg-green/10 px-2 py-1 text-green">▲ fresher legs</li>
                    <li className="rounded-md bg-red/10 px-2 py-1 text-red">▼ chose the riskier option</li>
                  </ul>
                </div>
                <div className="rounded-2xl border border-l-4 border-line border-l-hil bg-surface p-5 shadow-sm">
                  <p className="text-xs font-medium uppercase tracking-wide text-muted">Fan</p>
                  <p className="mt-3 text-lg leading-snug">
                    A fresh centre-back would have been <strong className="text-green">much more likely</strong> to win
                    that header.
                  </p>
                </div>
              </div>
            </Reveal>
          </div>
        </section>

        {/* how to use it */}
        <section className="mx-auto max-w-[1280px] px-4 pb-24 lg:px-8">
          <Reveal>
            <ol className="grid gap-4 md:grid-cols-3">
              {[
                ["Watch live", "The match plays on the board in real time, with both benches and the timeline.", "live"],
                ["Tap a moment", "Every key moment gets a card; replay it and see the options on the pitch.", "live"],
                ["Read the recap", "At full time the story of the match scrolls past, turning point first.", "recap"],
              ].map(([t, d, r], n) => (
                <li key={t}>
                  <a
                    href={href(r as "live" | "recap")}
                    className="group flex h-full flex-col rounded-2xl border border-line bg-surface p-6 shadow-sm transition-colors hover:border-line-2"
                  >
                    <span className="num text-sm text-amber">0{n + 1}</span>
                    <span className="mt-2 flex items-center gap-2 font-display text-lg font-semibold tracking-tight">
                      {t}
                      <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
                    </span>
                    <span className="mt-2 text-sm leading-relaxed text-ink/75">{d}</span>
                  </a>
                </li>
              ))}
            </ol>
          </Reveal>
        </section>

        {/* closing band */}
        <section className="chrome bg-chrome">
          <div className="mx-auto flex max-w-[1280px] flex-col items-start gap-6 px-4 py-16 lg:flex-row lg:items-center lg:justify-between lg:px-8">
            <div>
              <p className="flex items-center gap-2 text-sm text-muted">
                <RouteIcon className="size-4" aria-hidden /> A fully synthetic match
              </p>
              <p className="mt-2 font-display text-2xl font-semibold tracking-tight lg:text-3xl">
                {home?.name ?? "Riverside FC"} v {away?.name ?? "Hillton United"} is on now.
              </p>
            </div>
            <a
              href={href("live")}
              className="inline-flex items-center gap-2 rounded-lg bg-white px-5 py-3 text-sm font-medium text-chrome transition-colors hover:bg-white/85"
            >
              Watch the live match <ArrowRight className="size-4" aria-hidden />
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}
