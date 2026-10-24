import type { MomentAnalysis, PlayerProfile, TrackingFrame } from "@/types/contracts";
import { surname, svgY } from "@/lib/format";
import { ArrowMarkers, MomentLayer } from "./MomentLayer";
import { PITCH, PitchMarkings } from "./Pitch";

const R = 1.15;

interface Props {
  frame: TrackingFrame | null;
  players: Record<string, PlayerProfile>;
  homeTeam?: string;
  analysis?: MomentAnalysis | null;
  showLayer?: boolean;
  highlight?: string[];
  fan?: boolean;
  label?: string;
}

/** One frame of the pitch, drawn from props: the recap story moves it with the scroll. */
export function StaticBoard({
  frame,
  players,
  homeTeam,
  analysis,
  showLayer = false,
  highlight = [],
  fan = false,
  label,
}: Props) {
  const hl = new Set(highlight);
  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-panel-2 shadow-md">
      <svg
        viewBox={`-3 -3 ${PITCH.length + 6} ${PITCH.width + 6}`}
        className="block h-auto w-full select-none"
        role="img"
        aria-label={label ?? "Replay of a key moment"}
      >
        <ArrowMarkers />
        <PitchMarkings />
        {showLayer ? <MomentLayer analysis={analysis ?? null} fan={fan} /> : null}
        {frame?.players.map((t) => {
          const p = players[t.id];
          if (!p) return null;
          const home = p.team_id === homeTeam;
          return (
            <g key={t.id} transform={`translate(${t.x.toFixed(2)} ${svgY(t.y).toFixed(2)})`}>
              {hl.has(t.id) ? <circle r={R * 1.75} fill="none" stroke="var(--amber)" strokeWidth={0.18} /> : null}
              <circle
                r={R}
                fill={home ? "var(--ink)" : "var(--surface)"}
                stroke="var(--ink)"
                strokeWidth={home ? 0 : 0.28}
              />
              <text
                y={0.4}
                textAnchor="middle"
                fontSize={1.08}
                className="num"
                fontWeight={500}
                fill={home ? "var(--surface)" : "var(--ink)"}
              >
                {p.shirt_number}
              </text>
              {hl.has(t.id) ? (
                <text
                  y={-R - 1.3}
                  textAnchor="middle"
                  fontSize={1.3}
                  fontWeight={600}
                  fill="var(--ink)"
                  stroke="var(--panel-2)"
                  strokeWidth={0.5}
                  paintOrder="stroke"
                >
                  {surname(p.name)}
                </text>
              ) : null}
            </g>
          );
        })}
        {frame ? (
          <circle
            cx={frame.ball.x}
            cy={svgY(frame.ball.y) - frame.ball.z * 0.09}
            r={0.55 + frame.ball.z * 0.03}
            fill="var(--amber)"
            stroke="var(--surface)"
            strokeWidth={0.12}
          />
        ) : null}
      </svg>
    </div>
  );
}
