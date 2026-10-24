/** Flat pitch markings in metres (105 x 68), drawn in SVG user units with y pointing down. */
export const PITCH = { length: 105, width: 68 };

const box = (x: number, w: number, h: number) => ({ x, y: (PITCH.width - h) / 2, w, h });

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
    <g fill="none" stroke="var(--line-2)" strokeWidth={0.18} strokeLinecap="round">
      <rect x={0} y={0} width={L} height={W} rx={0.4} />
      <line x1={L / 2} y1={0} x2={L / 2} y2={W} />
      <circle cx={L / 2} cy={W / 2} r={9.15} />
      <circle cx={L / 2} cy={W / 2} r={0.3} fill="var(--line-2)" stroke="none" />
      {[...pen, ...six].map((b, i) => (
        <rect key={i} x={b.x} y={b.y} width={b.w} height={b.h} />
      ))}
      {goals.map((b, i) => (
        <rect key={`g${i}`} x={b.x} y={b.y} width={b.w} height={b.h} strokeWidth={0.25} />
      ))}
      <circle cx={11} cy={W / 2} r={0.3} fill="var(--line-2)" stroke="none" />
      <circle cx={L - 11} cy={W / 2} r={0.3} fill="var(--line-2)" stroke="none" />
      <path d={arc(11, 1)} />
      <path d={arc(L - 11, -1)} />
    </g>
  );
}
