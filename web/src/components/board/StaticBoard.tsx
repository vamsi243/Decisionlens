import type { MomentAnalysis, PlayerProfile, TrackingFrame } from "@/types/contracts";
import { surname, svgY } from "@/lib/format";
import { ArrowMarkers, MomentLayer } from "./MomentLayer";
import { DISC as R, NameTag, PITCH, PitchMarkings, PitchSurface, PlayerDisc } from "./Pitch";

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
    <div className="relative overflow-hidden rounded-xl border-[6px] border-chrome bg-[var(--pitch-2)] shadow-md">
      <svg
        viewBox={`-3 -3 ${PITCH.length + 6} ${PITCH.width + 6}`}
        className="block h-auto w-full select-none"
        role="img"
        aria-label={label ?? "Replay of a key moment"}
      >
        <ArrowMarkers />
        <PitchSurface />
        <PitchMarkings />
        {showLayer ? <MomentLayer analysis={analysis ?? null} fan={fan} /> : null}
        {frame?.players.map((t) => {
          const p = players[t.id];
          if (!p) return null;
          const home = p.team_id === homeTeam;
          return (
            <g key={t.id} transform={`translate(${t.x.toFixed(2)} ${svgY(t.y).toFixed(2)})`}>
              {hl.has(t.id) ? <circle r={R * 1.75} fill="none" stroke="var(--on-pitch)" strokeWidth={0.22} /> : null}
              <PlayerDisc home={home} number={p.shirt_number} />
              <NameTag strong={hl.has(t.id)}>{surname(p.name)}</NameTag>
            </g>
          );
        })}
        {frame ? (
          <circle
            cx={frame.ball.x}
            cy={svgY(frame.ball.y) - frame.ball.z * 0.09}
            r={0.55 + frame.ball.z * 0.03}
            fill="#fff"
            stroke="var(--chrome)"
            strokeWidth={0.14}
          />
        ) : null}
      </svg>
    </div>
  );
}
