import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import type { TeamStats, WorkloadState } from "@/types/contracts";
import { pct, surname } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { Sheet, SheetContent } from "./ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

const ROWS: { label: string; get: (t: TeamStats) => string }[] = [
  { label: "Passes", get: (t) => String(t.passes) },
  { label: "Pass accuracy", get: (t) => pct(t.pass_accuracy) },
  { label: "Avg pass length", get: (t) => `${t.avg_pass_distance_m.toFixed(1)} m` },
  { label: "Avg pass speed", get: (t) => `${(t.avg_pass_speed_ms * 3.6).toFixed(0)} km/h` },
  { label: "Shots (on target)", get: (t) => `${t.shots} (${t.shots_on_target})` },
  { label: "xG", get: (t) => t.xg.toFixed(2) },
  { label: "Fastest shot", get: (t) => `${(t.max_shot_speed_ms * 3.6).toFixed(0)} km/h` },
  { label: "Tackles won", get: (t) => String(t.tackles_won) },
  { label: "Interceptions", get: (t) => String(t.interceptions) },
  { label: "Distance", get: (t) => `${t.distance_km.toFixed(1)} km` },
];

function TeamTab() {
  const stats = useMatch((s) => s.stats);
  const meta = useMatch((s) => s.meta);
  const [h, a] = stats?.teams ?? [];
  if (!h || !a || !meta) return <p className="text-sm text-muted">Stats appear once the match is running.</p>;
  return (
    <div>
      <div className="flex justify-between text-sm font-medium">
        <span>{meta.teams[0]?.name}</span>
        <span>{meta.teams[1]?.name}</span>
      </div>
      <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-panel-2" aria-label="Possession">
        <div className="bg-ink" style={{ width: pct(h.possession) }} />
      </div>
      <div className="num mt-1 flex justify-between text-xs text-muted">
        <span>{pct(h.possession)}</span>
        <span>possession</span>
        <span>{pct(a.possession)}</span>
      </div>
      <dl className="mt-4 divide-y divide-line">
        {ROWS.map((r) => (
          <div key={r.label} className="grid grid-cols-[1fr_auto_1fr] items-center py-2 text-sm">
            <dd className="num">{r.get(h)}</dd>
            <dt className="text-xs text-muted">{r.label}</dt>
            <dd className="num text-right">{r.get(a)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const STATUS_COLOUR: Record<WorkloadState["status"], string> = {
  fit: "bg-green",
  tiring: "bg-amber",
  fatigued: "bg-red",
  knock: "bg-red",
};

function PlayersTab() {
  const workload = useMatch((s) => s.workload);
  const players = useMatch((s) => s.players);
  const meta = useMatch((s) => s.meta);
  const onPitch = useMatch((s) => s.onPitch);
  const [team, setTeam] = useState(meta?.teams[0]?.team_id ?? "");
  const rows = useMemo(
    () =>
      onPitch
        .map((id) => workload[id])
        .filter((w): w is WorkloadState => !!w && players[w.player_id]?.team_id === team)
        .sort((x, y) => y.fatigue - x.fatigue),
    [workload, players, onPitch, team],
  );
  return (
    <div>
      <ToggleGroup type="single" value={team} onValueChange={(v) => v && setTeam(v)} aria-label="Team">
        {meta?.teams.map((t) => (
          <ToggleGroupItem key={t.team_id} value={t.team_id}>
            {t.name}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <table className="mt-3 w-full text-sm">
        <thead className="text-left text-xs text-muted">
          <tr>
            <th className="py-1.5 font-normal">Player</th>
            <th className="py-1.5 text-right font-normal">Dist</th>
            <th className="py-1.5 text-right font-normal">HSR</th>
            <th className="py-1.5 text-right font-normal">Spr</th>
            <th className="w-[34%] py-1.5 pl-3 font-normal">Fatigue</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map((w) => {
            const p = players[w.player_id];
            return (
              <tr key={w.player_id}>
                <td className="py-1.5">
                  <span className="num mr-1.5 text-muted-2">{p?.shirt_number}</span>
                  {p ? surname(p.name) : w.player_id}
                </td>
                <td className="num py-1.5 text-right">{(w.distance_m / 1000).toFixed(1)}</td>
                <td className="num py-1.5 text-right">{Math.round(w.hsr_m)}</td>
                <td className="num py-1.5 text-right">{w.sprints}</td>
                <td className="py-1.5 pl-3">
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-panel-2">
                      <div className={cn("h-full rounded-full", STATUS_COLOUR[w.status])} style={{ width: `${w.fatigue}%` }} />
                    </div>
                    <span className="num w-6 text-right text-xs">{Math.round(w.fatigue)}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {rows.length === 0 ? <p className="mt-3 text-sm text-muted">Workload updates every 5 match seconds.</p> : null}
    </div>
  );
}

function IntensityTab() {
  const intensity = useMatch((s) => s.intensity);
  const moments = useMatch((s) => s.allMoments);
  const clockMs = useMatch((s) => s.clockMs);
  const data = intensity.map((p) => ({
    minute: Math.round(p.window_start_ms / 60000),
    index: p.index,
    current: p.window_start_ms <= clockMs && clockMs < p.window_end_ms,
  }));
  const marks = moments.filter((m) => m.type !== "fatigue_alert" && m.t_ms <= clockMs);
  return (
    <div>
      <p className="text-sm text-muted">Intensity per 5 minutes (0–100). Amber lines mark key moments.</p>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="minute" tick={{ fontSize: 11, fill: "var(--muted-2)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} tickFormatter={(m: number) => `${m}'`} type="number" domain={[0, 90]} ticks={[0, 15, 30, 45, 60, 75, 90]} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--muted-2)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} width={44} />
            <ChartTooltip cursor={{ fill: "var(--panel-2)" }} contentStyle={{ borderRadius: 12, border: "1px solid var(--line)", fontSize: 12 }} formatter={(v: number) => [v.toFixed(0), "intensity"]} labelFormatter={(m: number) => `${m}'–${m + 5}'`} />
            <Bar dataKey="index" radius={[4, 4, 0, 0]} barSize={14}>
              {data.map((d) => (
                <Cell key={d.minute} fill={d.current ? "var(--amber)" : "var(--ink)"} fillOpacity={d.current ? 1 : 0.8} />
              ))}
            </Bar>
            {marks.map((m) => (
              <ReferenceLine key={m.moment_id} x={m.t_ms / 60000} stroke="var(--amber)" strokeDasharray="3 3" />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function StatsDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title="Match stats" description="Every number here comes from the engine.">
        <Tabs defaultValue="team">
          <TabsList>
            <TabsTrigger value="team">Team</TabsTrigger>
            <TabsTrigger value="players">Workload</TabsTrigger>
            <TabsTrigger value="intensity">Intensity</TabsTrigger>
          </TabsList>
          <TabsContent value="team">
            <TeamTab />
          </TabsContent>
          <TabsContent value="players">
            <PlayersTab />
          </TabsContent>
          <TabsContent value="intensity">
            <IntensityTab />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
