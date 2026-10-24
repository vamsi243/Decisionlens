import { useRef, useState, type PointerEvent } from "react";
import type { KeyMoment } from "@/types/contracts";
import { api } from "@/lib/api";
import { clock, minute } from "@/lib/format";
import { playClip } from "@/lib/clip";
import { MOMENT_LABEL } from "@/lib/moments";
import { useMatch } from "@/state/match";
import { Tooltip } from "./ui/tooltip";

/**
 * Replay a moment. Locally the shared replay jumps to a few seconds before it; in a live
 * broadcast the viewer gets a personal clip instead (nobody else's board moves).
 */
export async function replayMoment(m: KeyMoment) {
  if (useMatch.getState().server?.live) return playClip(m);
  useMatch.getState().pin(m.moment_id);
  await api.seek(Math.max(0, m.frame_range.start * 100));
  await api.play();
}

/** The match timeline with key-moment markers; it sits in the table frame under the pitch. */
export function Scrubber() {
  const status = useMatch((s) => s.status);
  const meta = useMatch((s) => s.meta);
  const clockMs = useMatch((s) => s.clockMs);
  const moments = useMatch((s) => s.allMoments);
  const live = useMatch((s) => s.server?.live ?? false);
  const bar = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<number | null>(null);

  const duration = status?.duration_ms || 5_400_000;
  const shown = drag ?? clockMs;
  const toMs = (clientX: number) => {
    const r = bar.current?.getBoundingClientRect();
    if (!r) return 0;
    return Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * duration;
  };
  const onDown = (e: PointerEvent) => {
    if (live) return; // a live broadcast can't be scrubbed; markers play personal clips
    (e.target as Element).setPointerCapture(e.pointerId);
    setDrag(toMs(e.clientX));
  };
  const onMove = (e: PointerEvent) => drag !== null && setDrag(toMs(e.clientX));
  const onUp = (e: PointerEvent) => {
    if (drag === null) return;
    const t = toMs(e.clientX);
    setDrag(null);
    useMatch.getState().pin(null);
    void api.seek(t);
  };

  const halftime = (meta?.period_length_ms ?? 2_700_000) / duration;
  const visible = moments.filter((m) => m.type !== "fatigue_alert");

  return (
    <div className="chrome flex items-center gap-3 rounded-lg bg-panel-2 px-3 py-1.5">
        <span className="num w-12 text-xs text-muted">{clock(shown)}</span>
        <div className="relative h-8 flex-1">
          <div
            ref={bar}
            role="slider"
            aria-label="Match timeline"
            data-live={live}
            aria-valuemin={0}
            aria-valuemax={duration}
            aria-valuenow={Math.round(shown)}
            aria-valuetext={clock(shown)}
            tabIndex={0}
            onKeyDown={(e) => {
              if (live) return;
              const step = e.shiftKey ? 60_000 : 10_000;
              if (e.key === "ArrowRight") void api.seek(clockMs + step);
              if (e.key === "ArrowLeft") void api.seek(clockMs - step);
            }}
            onPointerDown={onDown}
            onPointerMove={onMove}
            onPointerUp={onUp}
            className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 data-[live=true]:cursor-default cursor-pointer rounded-full bg-line-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/30"
          >
            <div className="h-full rounded-full bg-ink" style={{ width: `${(shown / duration) * 100}%` }} />
            <div
              className="absolute top-1/2 size-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-ink bg-surface shadow-sm"
              style={{ left: `${(shown / duration) * 100}%` }}
            />
          </div>
          <div className="pointer-events-none absolute top-0 h-full w-px bg-line-2" style={{ left: `${halftime * 100}%` }} />
          {visible.map((m) => (
            <Tooltip key={m.moment_id} label={`${minute(m.t_ms)} ${MOMENT_LABEL[m.type]} · ${m.title}`}>
              <button
                type="button"
                aria-label={`Replay ${MOMENT_LABEL[m.type]} at ${minute(m.t_ms)}`}
                onClick={() => void replayMoment(m)}
                className="absolute top-0 size-3 -translate-x-1/2 rotate-45 rounded-[3px] bg-amber shadow-sm ring-2 ring-panel-2 transition-transform duration-200 hover:scale-125 focus-visible:outline-none focus-visible:ring-ink/40"
                style={{ left: `${(m.t_ms / duration) * 100}%` }}
              />
            </Tooltip>
          ))}
        </div>
        <span className="num w-12 text-right text-xs text-muted-2">{clock(duration)}</span>
    </div>
  );
}
