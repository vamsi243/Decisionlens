import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { Table } from "@/components/board/Table";
import { MomentFeed } from "@/components/MomentFeed";
import { PlayerPanel } from "@/components/PlayerPanel";
import { ResizableSplit } from "@/components/ui/resizable";
import { SettingsSheet } from "@/components/SettingsSheet";
import { TopBar } from "@/components/TopBar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useRoute } from "@/lib/router";
import { watchPrefsForSound } from "@/lib/sfx";
import { connectStream } from "@/lib/stream";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";

/** When the replay crosses a key moment with an analysis, pause so the option map can be read. */
function usePauseAtMoments(enabled: boolean) {
  const pause = usePrefs((s) => s.pauseAtMoments) && enabled;
  const done = useRef(new Set<string>());
  useEffect(
    () =>
      useMatch.subscribe((s, prev) => {
        // A shared live broadcast can't be paused; viewers replay moments as personal clips.
        if (!pause || s.server?.live || !s.status?.playing || s.clockMs < prev.clockMs) return;
        for (const m of Object.values(s.seen)) {
          if (m.type === "fatigue_alert" || done.current.has(m.moment_id) || !s.analyses[m.moment_id]) continue;
          if (prev.clockMs < m.t_ms + 600 && s.clockMs >= m.t_ms + 600) {
            done.current.add(m.moment_id);
            useMatch.getState().pin(m.moment_id);
            void api.pause();
          }
        }
      }),
    [pause],
  );
}

// Charts are heavy (recharts): load the drawer only when it is first opened.
const StatsDrawer = lazy(() =>
  import("@/components/StatsDrawer").then((m) => ({ default: m.StatsDrawer })),
);
const RecapPage = lazy(() => import("@/pages/RecapPage").then((m) => ({ default: m.RecapPage })));
const HowPage = lazy(() => import("@/pages/HowPage").then((m) => ({ default: m.HowPage })));
// CopilotKit is large: the chat loads only on the live page, after the board.
const MatchCopilot = lazy(() => import("@/components/Copilot"));
const HomePage = lazy(() => import("@/pages/HomePage").then((m) => ({ default: m.HomePage })));

/** A swatch drawn on a scrap of grass, because that is where the real marks sit. */
function Grass({ children }: { children: ReactNode }) {
  return <span className="inline-grid h-3.5 w-6 place-items-center rounded-sm bg-[var(--pitch-1)]">{children}</span>;
}

function Legend() {
  const t = useT();
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 px-1 text-xs text-muted">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-riv ring-2 ring-[var(--riv-rim)]" /> Riverside FC
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-hil ring-2 ring-[var(--hil-rim)]" /> Hillton United
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Grass><span className="h-0.5 w-4 rounded bg-white" /></Grass> {t("best option")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Grass><span className="h-0.5 w-4 rounded border-t border-dashed border-white/70" /></Grass> {t("other options")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Grass><span className="size-2.5 rounded-full border border-dashed border-white" /></Grass> {t("what-if")}
      </span>
      <span className="inline-flex items-center gap-1.5">
        <Grass><span className="size-2 rounded-full border border-chrome bg-white" /></Grass> {t("ball")}
      </span>
    </div>
  );
}

export function App() {
  const route = useRoute();
  useEffect(() => connectStream(), []);
  useEffect(() => watchPrefsForSound(), []);
  usePauseAtMoments(route === "live");
  return (
    <TooltipProvider>
      {route === "live" ? (
        <LivePage />
      ) : (
        <Suspense fallback={<div className="min-h-dvh bg-bg" />}>
          {route === "recap" ? <RecapPage /> : route === "how" ? <HowPage /> : <HomePage />}
        </Suspense>
      )}
    </TooltipProvider>
  );
}

function LivePage() {
  const [stats, setStats] = useState(false);
  const [settings, setSettings] = useState(false);
  const boardSize = usePrefs((s) => s.boardSize);
  const t = useT();
  const setPrefs = usePrefs((s) => s.set);
  return (
    <>
      <div className="flex min-h-dvh flex-col bg-bg">
        <TopBar />
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-6 lg:px-8 lg:py-8">
          <div className="rounded-3xl border border-line bg-surface p-4 shadow-sm lg:p-6">
            <ResizableSplit
              size={boardSize}
              onSize={(v) => setPrefs({ boardSize: v })}
              left={
                <section aria-label={t("Tactics table")}>
                  <Table onStats={() => setStats(true)} onSettings={() => setSettings(true)} />
                  <Legend />
                  <Suspense fallback={<div className="mt-6 h-[520px] rounded-2xl border border-line bg-surface" />}>
                    <MatchCopilot />
                  </Suspense>
                </section>
              }
              right={
                // Matches the table's height on wide screens; the feed scrolls inside it.
                <aside className="flex h-[70vh] min-h-[360px] flex-col rounded-2xl bg-bg p-4 lg:absolute lg:inset-0 lg:h-auto">
                  <MomentFeed />
                </aside>
              }
            />
          </div>
        </main>
      </div>
      {stats ? (
        <Suspense fallback={null}>
          <StatsDrawer open={stats} onOpenChange={setStats} />
        </Suspense>
      ) : null}
      <SettingsSheet open={settings} onOpenChange={setSettings} />
      <PlayerPanel />
    </>
  );
}
