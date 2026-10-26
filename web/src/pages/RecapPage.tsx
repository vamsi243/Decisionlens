import { motion, useMotionValueEvent, useScroll } from "framer-motion";
import { ArrowDown, ArrowRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { KeyMoment, Overlay, TrackingFrame } from "@/types/contracts";
import { StaticBoard } from "@/components/board/StaticBoard";
import { bullets, narration, PointList, SourceBadge, type Point } from "@/components/MomentCard";
import { PageHeader } from "@/components/Nav";
import { api } from "@/lib/api";
import { clock, midSentence, pct } from "@/lib/format";
import { MOMENT_LABEL } from "@/lib/moments";
import { href } from "@/lib/router";
import { useLenis } from "@/lib/useLenis";
import { useT } from "@/lib/i18n";
import { useTr } from "@/lib/tr";
import { swingWords } from "@/lib/words";
import { ensureAnalyses, ensureTranslations, useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";

interface TurningPoint {
  moment_id: string;
  minute: number;
  type: string;
  title: string;
}

/** One scroll chapter; reports how far through it the reader is (0 at the top, 1 at the end). */
function Chapter({
  index,
  onProgress,
  children,
}: {
  index: number;
  onProgress: (i: number, p: number) => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.6", "end 0.6"] });
  useMotionValueEvent(scrollYProgress, "change", (p) => {
    if (p > 0 && p < 1) onProgress(index, p);
  });
  return (
    <section ref={ref} data-snap className="flex min-h-[110vh] items-start py-16 lg:min-h-[130vh]">
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ amount: 0.4 }}
        transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
        className="w-full lg:sticky lg:top-28"
      >
        {children}
      </motion.div>
    </section>
  );
}

type Facts = Record<string, unknown>;
const list = <T,>(v: unknown) => (Array.isArray(v) ? (v as T[]) : []);

/** The full-time story as green / red points, straight from the engine's recap facts. */
function recapPoints(f: Facts, fan: boolean): Point[] {
  const out: Point[] = [];
  for (const g of list<{ minute: number; team: string; scorer: string }>(f.goals)) {
    out.push({ key: `g${g.minute}${g.scorer}`, up: true, text: `${g.minute}' ${g.scorer} scores for ${g.team}` });
  }
  const turning = list<{ minute: number; title: string; what_if?: { actual: number; swap: string; with_swap: number } }>(
    f.turning_points,
  ).filter((t) => t.what_if);
  for (const t of turning.slice(0, 2)) {
    const w = t.what_if!;
    const swap = w.swap.replace(" (fresh sub)", "");
    out.push({
      key: `t${t.minute}${t.title}`,
      up: false,
      text: fan
        ? `${t.minute}' ${t.title}: ${swap} could have changed it`
        : `${t.minute}' ${t.title}: ${pct(w.actual)} → ${pct(w.with_swap)} with ${swap}`,
    });
  }
  const teams = list<{ team: string; xg: number }>(f.teams);
  if (!fan && teams.length === 2) {
    const [a, b] = [...teams].sort((x, y) => y.xg - x.xg);
    out.push({ key: "xg", up: true, text: `${a!.team} made the better chances: ${a!.xg.toFixed(2)} xG to ${b!.xg.toFixed(2)}` });
  }
  const run = list<{ player: string; km: number }>(f.furthest_running)[0];
  if (run) out.push({ key: "run", up: true, text: fan ? `${run.player} ran furthest` : `${run.player} ran furthest: ${run.km} km` });
  const tire = list<{ player: string; fatigue: number }>(f.most_fatigued)[0];
  if (tire)
    out.push({ key: "tired", up: false, text: fan ? `${tire.player} ran out of legs` : `${tire.player} finished on fatigue ${Math.round(tire.fatigue)}` });
  return out;
}

export function RecapPage() {
  useLenis();
  const meta = useMatch((s) => s.meta);
  const players = useMatch((s) => s.players);
  const allMoments = useMatch((s) => s.allMoments);
  const analyses = useMatch((s) => s.analyses);
  const overlays = useMatch((s) => s.overlays);
  const persona = usePrefs((s) => s.persona);
  const lang = usePrefs((s) => s.language);
  const t = useT();
  const tr = useTr();
  const fan = persona === "fan";

  const [recap, setRecap] = useState<Overlay | null>(null);
  const [error, setError] = useState(false);
  const [frames, setFrames] = useState<Record<string, TrackingFrame[]>>({});
  const [active, setActive] = useState<{ i: number; p: number }>({ i: 0, p: 0 });

  useEffect(() => {
    api
      .recap()
      .then((o) => {
        setRecap(o);
        useMatch.getState().overlay(o);
      })
      .catch(() => setError(true));
  }, []);

  const points = useMemo(() => {
    const tps = (recap?.payload?.turning_points ?? []) as TurningPoint[];
    return [...tps].sort((a, b) => a.minute - b.minute);
  }, [recap]);
  // The turning points as moments: in a live broadcast the board only knows the ones so far.
  const [recapMoments, setRecapMoments] = useState<KeyMoment[]>([]);
  useEffect(() => {
    if (!recap) return;
    api
      .recapMoments()
      .then(setRecapMoments)
      .catch(() => undefined);
  }, [recap]);
  const byId = useMemo(
    () => new Map([...allMoments, ...recapMoments].map((m) => [m.moment_id, m])),
    [allMoments, recapMoments],
  );
  const moments = points.map((tp) => byId.get(tp.moment_id)).filter((m): m is KeyMoment => !!m);

  const momentKey = moments.map((m) => m.moment_id).join();
  useEffect(() => ensureAnalyses(moments), [momentKey]);
  useEffect(() => {
    for (const tp of points) {
      if (frames[tp.moment_id]) continue;
      api
        .frames(tp.moment_id, 1, true)
        .then((fs) => setFrames((f) => ({ ...f, [tp.moment_id]: fs })))
        .catch(() => undefined);
    }
  }, [points]);
  useEffect(() => {
    const ids = [recap?.overlay_id ?? "", ...points.map((p) => `ov_${p.moment_id}`)].filter(Boolean);
    ensureTranslations(ids, lang);
  }, [recap, points, lang, overlays]);

  const current = moments[active.i];
  const fs = current ? frames[current.moment_id] ?? [] : [];
  const fi = Math.min(fs.length - 1, Math.max(0, Math.round(active.p * (fs.length - 1))));
  const frame = fs[fi] ?? null;
  const momentFrame = current ? current.t_ms / 100 - current.frame_range.start : 0;
  const showLayer = !!current && fi >= momentFrame - 5;
  const [home, away] = meta?.teams ?? [];
  const score = (recap?.payload?.score ?? {}) as Record<string, number>;
  const recapText = narration(recap ? overlays[recap.overlay_id] ?? recap : undefined, persona, lang);
  const runners = (recap?.payload?.furthest_running ?? []) as { player: string; km: number }[];
  const tired = (recap?.payload?.most_fatigued ?? []) as { player: string; fatigue: number }[];
  const story = recapPoints(recap?.payload ?? {}, fan);

  return (
    <div className="min-h-dvh bg-bg">
      <PageHeader route="recap" />
      <div className="mx-auto grid max-w-[1500px] gap-6 px-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:gap-12 lg:px-6">
        {/* The pitch stays pinned while the story scrolls past it. */}
        <div className="sticky top-[60px] z-10 -mx-4 bg-bg/90 px-4 pb-3 pt-3 backdrop-blur lg:top-[84px] lg:mx-0 lg:h-fit lg:bg-transparent lg:p-0 lg:pt-8 lg:backdrop-blur-0">
          <StaticBoard
            frame={frame}
            players={players}
            homeTeam={home?.team_id}
            analysis={current ? analyses[current.moment_id] : null}
            showLayer={showLayer}
            highlight={current?.players ?? []}
            fan={fan}
            label={current ? t("Replay: {moment}", { moment: tr(current.title) }) : t("Pitch")}
          />
          <div className="mt-2 flex items-center justify-between text-xs text-muted">
            <span>{current ? `${t(MOMENT_LABEL[current.type])} · ${tr(current.title)}` : t("Scroll to replay the turning points")}</span>
            <span className="num">{frame ? clock(frame.t_ms) : ""}</span>
          </div>
          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-line" aria-hidden>
            <div className="h-full bg-key transition-[width] duration-100" style={{ width: `${active.p * 100}%` }} />
          </div>
        </div>

        <main className="pb-24">
          <section data-snap className="flex min-h-[80vh] flex-col justify-center py-16">
            <p className="text-sm font-medium uppercase tracking-wide text-key">{t("Full time")}</p>
            <h1 className="mt-3 font-display text-4xl font-extrabold tracking-tight lg:text-5xl">
              {home?.name ?? "Riverside FC"}{" "}
              <span className="tabular-nums">
                {score[home?.name ?? ""] ?? "–"}–{score[away?.name ?? ""] ?? "–"}
              </span>{" "}
              {away?.name ?? "Hillton United"}
            </h1>
            {error ? (
              <p className="mt-6 text-muted">{t("The recap needs the stream service; is it running?")}</p>
            ) : (
              <div className="mt-8 max-w-xl">
                {fan && recapText ? <p className="mb-4 text-xl leading-snug">{recapText}</p> : null}
                {story.length ? <PointList points={story} fan={fan} /> : <p className="text-muted">{t("Writing the recap…")}</p>}
                {!fan && recapText ? (
                  <details className="mt-4">
                    <summary className="cursor-pointer select-none text-sm font-medium text-muted hover:text-ink">
                      {t("Read the recap")}
                    </summary>
                    <p className="mt-2 leading-relaxed text-ink/85">{recapText}</p>
                  </details>
                ) : null}
              </div>
            )}
            <div className="mt-4">
              <SourceBadge overlay={recap ?? undefined} />
            </div>
            <p className="mt-10 inline-flex items-center gap-2 text-sm text-muted">
              <ArrowDown className="size-4 animate-bounce" aria-hidden /> {t("Scroll to relive the {n} turning points", { n: moments.length })}
            </p>
          </section>

          {moments.map((m, i) => {
            const a = analyses[m.moment_id];
            const w = a?.what_if;
            const text = narration(overlays[`ov_${m.moment_id}`], persona, lang);
            return (
              <Chapter key={m.moment_id} index={i} onProgress={(idx, p) => setActive({ i: idx, p })}>
                <article className="rounded-xl border border-line bg-surface p-6 shadow-lg">
                  <p className="text-xs text-muted">
                    <span className="num text-key">{Math.floor(m.t_ms / 60000) + 1}'</span> · {t(MOMENT_LABEL[m.type])}
                  </p>
                  <h2 className="mt-2 font-display text-2xl font-extrabold tracking-tight">{tr(m.title)}</h2>
                  {text && fan ? <p className="mt-3 text-lg leading-snug">{text}</p> : null}
                  {w ? (
                    fan ? (
                      <p className="mt-4 text-lg">
                        {t("With {swap}:", { swap: tr(w.counterfactual.profile.label.replace(" (fresh sub)", "")) })}{" "}
                        <strong className="text-green">{tr(swingWords(w.actual.p_success, w.counterfactual.p_success))}</strong>
                      </p>
                    ) : (
                      <div className="mt-4 flex items-baseline gap-3 rounded-md bg-panel-2 p-4">
                        <span className="num text-3xl">{pct(w.actual.p_success)}</span>
                        <ArrowRight className="size-5 text-muted" aria-hidden />
                        <span className="num text-3xl text-green">{pct(w.counterfactual.p_success)}</span>
                        <span className="ml-2 text-sm text-muted">{t("with {swap}", { swap: tr(midSentence(w.counterfactual.profile.label)) })}</span>
                      </div>
                    )
                  ) : null}
                  <PointList points={bullets(m, a, players, undefined, fan)} fan={fan} className="mt-4" />
                  {text && !fan ? (
                    <details className="mt-4" open={lang !== "en"}>
                      <summary className="cursor-pointer select-none text-xs font-medium text-muted hover:text-ink">
                        {t("Read the analysis")}
                      </summary>
                      <p className="mt-1.5 text-sm leading-relaxed text-ink/85">{text}</p>
                    </details>
                  ) : null}
                  <p className="mt-5 text-xs text-muted-2">{t("Keep scrolling: the pitch replays the moment.")}</p>
                </article>
              </Chapter>
            );
          })}

          <section data-snap className="flex min-h-[70vh] flex-col justify-center py-16">
            <h2 className="font-display text-3xl font-extrabold tracking-tight">{t("The physical story")}</h2>
            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-lg border border-line bg-surface p-5 shadow-sm">
                <p className="text-sm text-muted">{t("Ran furthest")}</p>
                <ul className="mt-2 space-y-1">
                  {runners.map((r) => (
                    <li key={r.player} className="flex justify-between">
                      <span>{r.player}</span>
                      <span className="num">{r.km} km</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-line bg-surface p-5 shadow-sm">
                <p className="text-sm text-muted">{t("Most fatigued")}</p>
                <ul className="mt-2 space-y-1">
                  {tired.map((r) => (
                    <li key={r.player} className="flex justify-between">
                      <span>{r.player}</span>
                      <span className="num text-amber">{Math.round(r.fatigue)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-10 flex flex-wrap gap-3">
              <a href={href("live")} className="rounded-md bg-ink px-4 py-2 text-sm font-medium text-surface">
                {t("Back to the live board")}
              </a>
              <a href={href("how")} className="rounded-md border border-line bg-surface px-4 py-2 text-sm font-medium">
                {t("How it works")}
              </a>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}
