import type { ReactNode } from "react";

/** Flat pitch markings in metres (105 x 68), drawn in SVG user units with y pointing down. */
export const PITCH = { length: 105, width: 68 };

const box = (x: number, w: number, h: number) => ({ x, y: (PITCH.width - h) / 2, w, h });

const STRIPES = 12;

/** Mown grass: alternating bands across the pitch, plus the run-off round it. */
export function PitchSurface() {
  const band = PITCH.length / STRIPES;
  return (
    <g aria-hidden>
      <rect x={-3} y={-3} width={PITCH.length + 6} height={PITCH.width + 6} fill="var(--pitch-2)" />
      {Array.from({ length: STRIPES }, (_, i) =>
        i % 2 ? null : <rect key={i} x={i * band} y={0} width={band} height={PITCH.width} fill="var(--pitch-1)" />,
      )}
    </g>
  );
}

export const DISC = 1.15; // player disc radius, metres

/** A domed player token in team colours, like a magnet on a tactics table. */
export function PlayerDisc({ home, number }: { home: boolean; number: number }) {
  return (
    <>
      <circle r={DISC * 1.2} fill={home ? "var(--riv-rim)" : "var(--hil-rim)"} />
      <circle r={DISC} fill={home ? "var(--riv)" : "var(--hil)"} />
      <circle cx={-0.38} cy={-0.42} r={0.36} fill="#fff" opacity={0.55} />
      <text
        y={0.42}
        textAnchor="middle"
        fontSize={1.08}
        className="num"
        fontWeight={600}
        fill={home ? "#fff" : "var(--hil-ink)"}
      >
        {number}
      </text>
    </>
  );
}

/** White label under a token, haloed so it reads on any stripe. */
export function NameTag({ children, strong = false }: { children: ReactNode; strong?: boolean }) {
  return (
    <text
      y={DISC + 2.05}
      textAnchor="middle"
      fontSize={strong ? 1.3 : 1.1}
      fontWeight={strong ? 600 : 500}
      fill="var(--on-pitch)"
      stroke="var(--on-pitch-halo)"
      strokeWidth={0.42}
      paintOrder="stroke"
    >
      {children}
    </text>
  );
}

export function PitchMarkings() {
  const L = PITCH.length;
  const W = PITCH.width;
  const pen = [box(0, 16.5, 40.32), box(L - 16.5, 16.5, 40.32)];
  const six = [box(0, 5.5, 18.32), box(L - 5.5, 5.5, 18.32)];
  const goals = [box(-1.6, 1.6, 7.32), box(L, 1.6, 7.32)];
  const arc = (cx: number, dir: 1 | -1) => {
    // the "D": the part of the 9.15 m circle round the penalty spot outside the box
    const dx = 16.5 - 11;
    const dy = Math.sqrt(9.15 ** 2 - dx ** 2);
    const x = cx + dir * dx;
    return `M ${x} ${W / 2 - dy} A 9.15 9.15 0 0 ${dir === 1 ? 1 : 0} ${x} ${W / 2 + dy}`;
  };
  return (
    <g fill="none" stroke="var(--pitch-line)" strokeWidth={0.22} strokeLinecap="round">
      <rect x={0} y={0} width={L} height={W} rx={0.4} />
      <line x1={L / 2} y1={0} x2={L / 2} y2={W} />
      <circle cx={L / 2} cy={W / 2} r={9.15} />
      <circle cx={L / 2} cy={W / 2} r={0.3} fill="var(--pitch-line)" stroke="none" />
      {[...pen, ...six].map((b, i) => (
        <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} />
      ))}
      {goals.map((b, i) => (
        <rect key={`g${i}`} x={b.x} y={b.y} width={b.w} height={b.h} strokeWidth={0.25} />
      ))}
      <circle cx={11} cy={W / 2} r={0.3} fill="var(--pitch-line)" stroke="none" />
      <circle cx={L - 11} cy={W / 2} r={0.3} fill="var(--pitch-line)" stroke="none" />
      <path d={arc(11, 1)} />
      <path d={arc(L - 11, -1)} />
    </g>
  );
}
