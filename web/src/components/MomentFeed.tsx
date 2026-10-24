import { ArrowDown } from "lucide-react";
import { AnimatePresence } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import { activeMoment } from "@/lib/moments";
import { ensureAnalyses, revealedMoments, useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { MomentCard } from "./MomentCard";
import { Button } from "./ui/button";

export function MomentFeed() {
  const seen = useMatch((s) => s.seen);
  const allMoments = useMatch((s) => s.allMoments);
  const clockMs = useMatch((s) => s.clockMs);
  const analyses = useMatch((s) => s.analyses);
  const players = useMatch((s) => s.players);
  const workload = useMatch((s) => s.workload);
  const pinned = useMatch((s) => s.pinned);
  const persona = usePrefs((s) => s.persona);
  const favPlayer = usePrefs((s) => s.player);
  const favClub = usePrefs((s) => s.club);

  const moments = useMemo(
    () => revealedMoments({ seen, allMoments, clockMs }),
    [seen, allMoments, clockMs],
  );
  useEffect(() => ensureAnalyses(moments), [moments]);
  const active = activeMoment(seen, analyses, clockMs, pinned)?.moment.moment_id;

  const box = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTo({ top: box.current.scrollHeight, behavior: "smooth" });
  }, [moments.length, follow]);

  return (
    <section className="relative flex min-h-0 flex-col" aria-label="Key moments">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-display text-sm font-semibold tracking-tight">Key moments</h2>
        <span className="num text-xs text-muted-2">{moments.length}</span>
      </div>
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget;
          setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
        }}
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-2 pr-1"
      >
        {moments.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-2 p-4 text-sm text-muted">
            Moments worth explaining appear here as the match plays.
          </p>
        ) : null}
        <AnimatePresence initial={false}>
          {moments.map((m) => (
            <MomentCard
              key={m.moment_id}
              moment={m}
              analysis={analyses[m.moment_id]}
              persona={persona}
              players={players}
              workload={workload}
              active={m.moment_id === active}
              favourite={
                (favPlayer !== null && m.players.includes(favPlayer)) ||
                (favClub !== null && m.team_id === favClub)
              }
            />
          ))}
        </AnimatePresence>
      </div>
      {!follow ? (
        <Button
          size="sm"
          variant="primary"
          className="absolute bottom-4 left-1/2 -translate-x-1/2 shadow-lg"
          onClick={() => setFollow(true)}
        >
          <ArrowDown className="size-3.5" /> Jump to live
        </Button>
      ) : null}
    </section>
  );
}
