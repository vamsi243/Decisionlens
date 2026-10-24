import { GripVertical } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const MIN = 40;
const MAX = 78;
const clamp = (v: number) => Math.min(MAX, Math.max(MIN, v));

/** True on screens wide enough for side-by-side panels (Tailwind's lg). */
function useWide() {
  const query = "(min-width: 1024px)";
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setWide(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return wide;
}

/**
 * Two panels side by side with a handle between them: drag it (or use the arrow keys) to make
 * the left panel bigger or smaller. Stacked, without a handle, on narrow screens.
 */
export function ResizableSplit({
  left,
  right,
  size,
  onSize,
}: {
  left: ReactNode;
  right: ReactNode;
  size: number; // left panel width, % of the row
  onSize: (pct: number) => void;
}) {
  const wide = useWide();
  const t = useT();
  const row = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const at = (clientX: number) => {
    const r = row.current?.getBoundingClientRect();
    if (r) onSize(clamp(((clientX - r.left) / r.width) * 100));
  };
  const down = (e: PointerEvent) => {
    (e.target as Element).setPointerCapture(e.pointerId);
    setDragging(true);
  };
  const move = (e: PointerEvent) => dragging && at(e.clientX);
  const up = () => setDragging(false);
  const key = (e: KeyboardEvent) => {
    const step = e.shiftKey ? 6 : 2;
    if (e.key === "ArrowLeft") onSize(clamp(size - step));
    if (e.key === "ArrowRight") onSize(clamp(size + step));
    if (e.key === "Home") onSize(MIN);
    if (e.key === "End") onSize(MAX);
  };

  if (!wide) {
    return (
      <div className="flex flex-col gap-6">
        {left}
        {right}
      </div>
    );
  }
  return (
    <div ref={row} className={cn("flex items-stretch", dragging && "cursor-col-resize select-none")}>
      <div className="min-w-0 shrink-0" style={{ width: `${size}%` }}>
        {left}
      </div>
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={t("Resize the pitch")}
        aria-valuemin={MIN}
        aria-valuemax={MAX}
        aria-valuenow={Math.round(size)}
        tabIndex={0}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        onKeyDown={key}
        onDoubleClick={() => onSize(64)}
        title={t("Drag to resize the pitch (double-click to reset)")}
        className="group relative mx-2 flex w-4 shrink-0 cursor-col-resize items-center justify-center outline-none"
      >
        <span
          className={cn(
            "h-full w-px bg-line-2 transition-colors group-hover:bg-ink/40 group-focus-visible:bg-ink/60",
            dragging && "bg-ink/60",
          )}
        />
        <span
          className={cn(
            "absolute grid h-10 w-4 place-items-center rounded-md border border-line bg-surface text-muted shadow-sm transition-colors group-hover:text-ink group-focus-visible:ring-2 group-focus-visible:ring-ink/30",
            dragging && "text-ink",
          )}
        >
          <GripVertical className="size-3.5" aria-hidden />
        </span>
      </div>
      <div className="relative min-w-0 flex-1">{right}</div>
    </div>
  );
}
