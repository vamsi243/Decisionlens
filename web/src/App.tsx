import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Board } from "@/components/board/Board";
import { MomentFeed } from "@/components/MomentFeed";
import { Scrubber } from "@/components/Scrubber";
import { SettingsSheet } from "@/components/SettingsSheet";
import { TopBar } from "@/components/TopBar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { api } from "@/lib/api";
import { useRoute } from "@/lib/router";
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
        if (!pause || !s.status?.playing || s.clockMs < prev.clockMs) return;
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

function Legend() {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full bg-ink" /> Riverside FC
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border-2 border-ink bg-surface" /> Hillton United
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded bg-green" /> best option
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2.5 rounded-full border border-dashed border-green" /> what-if
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="size-2 rounded-full bg-amber" /> ball · sprint badge
      </span>
    </div>
  );
}

export function App() {
  const route = useRoute();
  useEffect(() => connectStream(), []);
  usePauseAtMoments(route === "live");
  return (
    <TooltipProvider>
      {route === "live" ? (
        <LivePage />
      ) : (
        <Suspense fallback={<div className="min-h-dvh bg-bg" />}>
          {route === "recap" ? <RecapPage /> : <HowPage />}
        </Suspense>
      )}
    </TooltipProvider>
  );
}

function LivePage() {
  const [stats, setStats] = useState(false);
  const [settings, setSettings] = useState(false);
  return (
    <>
      <div className="flex min-h-dvh flex-col bg-bg">
        <TopBar onStats={() => setStats(true)} onSettings={() => setSettings(true)} />
        <main className="mx-auto grid w-full max-w-[1500px] flex-1 gap-5 px-4 py-5 lg:grid-cols-[minmax(0,1fr)_380px] lg:px-6">
          <section className="self-start lg:sticky lg:top-[84px]">
            <Board />
            <Legend />
          </section>
          <aside className="flex min-h-[320px] flex-col lg:h-[calc(100dvh-170px)] lg:sticky lg:top-[84px]">
            <MomentFeed />
          </aside>
        </main>
        <Scrubber />
      </div>
      {stats ? (
        <Suspense fallback={null}>
          <StatsDrawer open={stats} onOpenChange={setStats} />
        </Suspense>
      ) : null}
      <SettingsSheet open={settings} onOpenChange={setSettings} />
    </>
  );
}
