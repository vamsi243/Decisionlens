import { scaleLinear } from "d3-scale";
import { curveNatural, line } from "d3-shape";
import { motion, useReducedMotion } from "framer-motion";
import type { MomentAnalysis, Option, Point } from "@/types/contracts";
import { pct, svgY } from "@/lib/format";
import { swingWords } from "@/lib/words";

const width = scaleLinear().domain([0, 1]).range([0.18, 0.95]).clamp(true);
const curve = line<[number, number]>().curve(curveNatural);

/** A gently curved path from a to b (bulging to the left of travel). */
function bend(a: Point, b: Point, amount = 0.12): { d: string; mid: [number, number] } {
  const ax = a.x;
  const ay = svgY(a.y);
  const bx = b.x;
  const by = svgY(b.y);
  const dx = bx - ax;
  const dy = by - ay;
  const mid: [number, number] = [(ax + bx) / 2 - dy * amount, (ay + by) / 2 + dx * amount];
  return { d: curve([[ax, ay], mid, [bx, by]]) ?? "", mid };
}

function OptionArrow({
  o,
  best,
  index,
  fan,
}: {
  o: Option;
  best: boolean;
  index: number;
  fan: boolean;
}) {
  const reduce = useReducedMotion();
  const start = o.path[0];
  const end = o.path[o.path.length - 1];
  if (!start || !end) return null;
  const { d, mid } = bend(start, end);
  const colour = best ? "var(--on-pitch)" : "var(--on-pitch-dim)";
  return (
    <g>
      <motion.path
        d={d}
        fill="none"
        stroke={colour}
        strokeWidth={width(o.p_success)}
        strokeLinecap="round"
        strokeDasharray={o.chosen ? undefined : best ? undefined : "0.9 0.7"}
        markerEnd={`url(#arrow-${best ? "best" : "other"})`}
        initial={reduce ? false : { pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: best ? 1 : 0.85 }}
        transition={{ duration: 0.6, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      />
      {fan ? null : (
        <g transform={`translate(${mid[0]} ${mid[1]})`}>
          <rect x={-2.6} y={-1.15} width={5.2} height={2.1} rx={1} fill="var(--surface)" stroke={colour} strokeWidth={0.12} />
          <text textAnchor="middle" y={0.42} fontSize={1.25} className="num" fill={best ? "var(--green)" : "var(--ink)"}>
            {pct(o.p_success)}
          </text>
        </g>
      )}
      {o.chosen ? (
        <circle cx={end.x} cy={svgY(end.y)} r={1.9} fill="none" stroke="var(--on-pitch)" strokeWidth={0.14} strokeDasharray="0.4 0.35" />
      ) : null}
    </g>
  );
}

function Ghost({ a, fan }: { a: MomentAnalysis; fan: boolean }) {
  const w = a.what_if;
  const ghost = w?.ghost_path ?? [];
  const start = ghost[0];
  const end = ghost[ghost.length - 1];
  if (!w || !start || !end) return null;
  const { d } = bend(start, end, 0.05);
  return (
    <g>
      <path d={d} fill="none" stroke="var(--on-pitch)" strokeWidth={0.26} strokeDasharray="0.8 0.6" />
      <circle cx={end.x} cy={svgY(end.y)} r={1.25} fill="var(--on-pitch)" fillOpacity={0.25} stroke="var(--on-pitch)" strokeWidth={0.22} strokeDasharray="0.5 0.4" />
      <g transform={`translate(${end.x + 2.2} ${svgY(end.y) - 2.2})`}>
        <rect x={0} y={-1.3} width={fan ? 17 : 13} height={2.5} rx={1.2} fill="var(--surface)" stroke="var(--green)" strokeWidth={0.12} />
        {fan ? (
          <text x={8.5} y={0.42} textAnchor="middle" fontSize={1.3} fontWeight={600} fill="var(--green)">
            {swingWords(w.actual.p_success, w.counterfactual.p_success)}
          </text>
        ) : (
          <text x={6.5} y={0.42} textAnchor="middle" fontSize={1.3} className="num" fill="var(--ink)">
            {pct(w.actual.p_success)} → <tspan fill="var(--green)">{pct(w.counterfactual.p_success)}</tspan>
          </text>
        )}
      </g>
    </g>
  );
}

/** Option arrows + what-if ghost. Fans see only the best and chosen options, in words. */
export function MomentLayer({
  analysis,
  fan = false,
}: {
  analysis: MomentAnalysis | null;
  fan?: boolean;
}) {
  if (!analysis) return null;
  const opts = analysis.options;
  const shown = (opts?.options ?? []).filter(
    (o) => !fan || o.chosen || o.option_id === opts?.best_option_id,
  );
  return (
    <motion.g key={analysis.moment.moment_id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      {shown.map((o, i) => (
        <OptionArrow key={o.option_id} o={o} best={o.option_id === opts?.best_option_id} index={i} fan={fan} />
      ))}
      <Ghost a={analysis} fan={fan} />
    </motion.g>
  );
}

export function ArrowMarkers() {
  return (
    <defs>
      {[
        ["best", "var(--on-pitch)"],
        ["other", "var(--on-pitch-dim)"],
      ].map(([id, c]) => (
        <marker key={id} id={`arrow-${id}`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="3.2" markerHeight="3.2" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
        </marker>
      ))}
    </defs>
  );
}
