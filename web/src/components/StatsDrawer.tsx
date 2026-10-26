import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip as ChartTooltip, XAxis, YAxis, ZAxis } from "recharts";
import type { CalibrationReport, IntensityPoint, TeamStats, WorkloadState } from "@/types/contracts";
import { Download } from "lucide-react";
import { api } from "@/lib/api";
import { downloadJson } from "@/lib/export";
import { pct, surname } from "@/lib/format";
import { cn } from "@/lib/utils";
import { msg, useT } from "@/lib/i18n";
import { useMatch } from "@/state/match";
import { Sheet, SheetContent } from "./ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

const ROWS: { label: string; get: (t: TeamStats) => string }[] = [
  { label: msg("Passes"), get: (t) => String(t.passes) },
  { label: msg("Pass accuracy"), get: (t) => pct(t.pass_accuracy) },
  { label: msg("Avg pass length"), get: (t) => `${t.avg_pass_distance_m.toFixed(1)} m` },
  { label: msg("Avg pass speed"), get: (t) => `${(t.avg_pass_speed_ms * 3.6).toFixed(0)} km/h` },
  { label: msg("Shots (on target)"), get: (t) => `${t.shots} (${t.shots_on_target})` },
  { label: "xG", get: (t) => t.xg.toFixed(2) },
  { label: msg("Fastest shot"), get: (t) => `${(t.max_shot_speed_ms * 3.6).toFixed(0)} km/h` },
  { label: msg("Tackles won"), get: (t) => String(t.tackles_won) },
  { label: msg("Interceptions"), get: (t) => String(t.interceptions) },
  { label: msg("Distance"), get: (t) => `${t.distance_km.toFixed(1)} km` },
];

function TeamTab() {
  const stats = useMatch((s) => s.stats);
  const meta = useMatch((s) => s.meta);
  const t = useT();
  const [h, a] = stats?.teams ?? [];
  if (!h || !a || !meta) return <p className="text-sm text-muted">{t("Stats appear once the match is running.")}</p>;
  return (
    <div>
      <div className="flex justify-between text-sm font-medium">
        <span>{meta.teams[0]?.name}</span>
        <span>{meta.teams[1]?.name}</span>
      </div>
      <div className="mt-2 flex h-2.5 overflow-hidden rounded-full bg-hil" aria-label={t("Possession")}>
        <div className="bg-riv" style={{ width: pct(h.possession) }} />
      </div>
      <div className="num mt-1 flex justify-between text-xs text-muted">
        <span>{pct(h.possession)}</span>
        <span>{t("possession")}</span>
        <span>{pct(a.possession)}</span>
      </div>
      <dl className="mt-4 divide-y divide-line">
        {ROWS.map((r) => (
          <div key={r.label} className="grid grid-cols-[1fr_auto_1fr] items-center py-2 text-sm">
            <dd className="num">{r.get(h)}</dd>
            <dt className="text-xs text-muted">{t(r.label)}</dt>
            <dd className="num text-right">{r.get(a)}</dd>
          </div>
        ))}
      </dl>
      <button
        type="button"
        onClick={() =>
          void api.overlays(true).then((os) => downloadJson(`decision-lens_${meta.match_id}_overlays.json`, os))
        }
        className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-line bg-surface px-3 py-1.5 text-xs shadow-sm hover:bg-panel-2"
      >
        <Download className="size-3.5" aria-hidden /> {t("Export every card (time-coded JSON for broadcast)")}
      </button>
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
  const t = useT();
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
      <ToggleGroup type="single" value={team} onValueChange={(v) => v && setTeam(v)} aria-label={t("Team")}>
        {meta?.teams.map((t) => (
          <ToggleGroupItem key={t.team_id} value={t.team_id}>
            {t.name}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <table className="mt-3 w-full text-sm">
        <thead className="text-left text-xs text-muted">
          <tr>
            <th className="py-1.5 font-normal">{t("Player")}</th>
            <th className="py-1.5 text-right font-normal">{t("Dist")}</th>
            <th className="py-1.5 text-right font-normal">{t("HSR")}</th>
            <th className="py-1.5 text-right font-normal">{t("Spr")}</th>
            <th className="w-[34%] py-1.5 pl-3 font-normal">{t("Fatigue")}</th>
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
      {rows.length === 0 ? <p className="mt-3 text-sm text-muted">{t("Workload updates every 5 match seconds.")}</p> : null}
    </div>
  );
}

type Rhythm = "chaos" | "pressure" | "control" | "steady";
const RHYTHM: Record<Rhythm, { label: string; why: string; cls: string }> = {
  chaos: { label: msg("Chaos"), why: msg("lots of duels and turnovers near goal"), cls: "bg-ink text-bg" },
  pressure: { label: msg("Pressure"), why: msg("one side pressing hard"), cls: "bg-ink/60 text-bg" },
  control: { label: msg("Control"), why: msg("a calm period with the ball kept"), cls: "bg-panel-2 text-ink" },
  steady: { label: msg("Steady"), why: msg("an even, ordinary period"), cls: "border border-line text-muted" },
};

/** The rhythm of each finished 5-minute window, ranked against the match so far (engine counts only). */
function rhythms(points: IntensityPoint[]): Rhythm[] {
  const at = (xs: number[], q: number) => [...xs].sort((a, b) => a - b)[Math.floor((xs.length - 1) * q)] ?? 0;
  const contest = points.map((p) => p.duels + 2 * p.dangerous_turnovers);
  const press = points.map((p) => p.pressures);
  const hiContest = at(contest, 2 / 3);
  const hiPress = at(press, 2 / 3);
  const loIndex = at(points.map((p) => p.index), 1 / 3);
  return points.map((p, i) => {
    if (contest[i]! > hiContest) return "chaos";
    if (press[i]! > hiPress) return "pressure";
    if (p.index <= loIndex) return "control";
    return "steady";
  });
}

function IntensityTab() {
  const intensity = useMatch((s) => s.intensity);
  const moments = useMatch((s) => s.allMoments);
  const clockMs = useMatch((s) => s.clockMs);
  const t = useT();
  const data = intensity.map((p) => ({
    minute: Math.round(p.window_start_ms / 60000),
    index: p.index,
    current: p.window_start_ms <= clockMs && clockMs < p.window_end_ms,
  }));
  const marks = moments.filter((m) => m.type !== "fatigue_alert" && m.t_ms <= clockMs);
  const done = intensity.filter((p) => p.window_end_ms <= clockMs);
  const rhythm = rhythms(done);
  const pending = intensity.length - done.length;
  const now = rhythm.at(-1);
  const before = rhythm.at(-2);
  return (
    <div>
      <p className="text-sm text-muted">{t("Intensity per 5 minutes (0–100). Dashed lines mark key moments.")}</p>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -20 }}>
            <CartesianGrid vertical={false} stroke="var(--line)" />
            <XAxis dataKey="minute" tick={{ fontSize: 11, fill: "var(--muted-2)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} tickFormatter={(m: number) => `${m}'`} type="number" domain={[0, 90]} ticks={[0, 15, 30, 45, 60, 75, 90]} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--muted-2)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} width={44} />
            <ChartTooltip cursor={{ fill: "var(--panel-2)" }} contentStyle={{ borderRadius: 12, border: "1px solid var(--line)", fontSize: 12 }} formatter={(v: number) => [v.toFixed(0), t("intensity")]} labelFormatter={(m: number) => `${m}'–${m + 5}'`} />
            <Bar dataKey="index" radius={[4, 4, 0, 0]} barSize={14}>
              {data.map((d) => (
                <Cell key={d.minute} fill={d.current ? "var(--key)" : "var(--ink)"} fillOpacity={d.current ? 1 : 0.8} />
              ))}
            </Bar>
            {marks.map((m) => (
              <ReferenceLine key={m.moment_id} x={m.t_ms / 60000} stroke="var(--key)" strokeDasharray="3 3" />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      {done.length >= 3 ? (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">{t("Rhythm: control or chaos?")}</h3>
          <div className="mt-2 ml-6 mr-1 grid grid-cols-18 gap-0.5" aria-hidden>
            {rhythm.map((r, i) => (
              <span
                key={done[i]!.window_start_ms}
                title={`${Math.round(done[i]!.window_start_ms / 60000)}': ${t(RHYTHM[r].label)}`}
                style={{ gridColumnStart: Math.round(done[i]!.window_start_ms / 300_000) + 1 }}
                className={cn("h-5 rounded-sm", RHYTHM[r].cls)}
              />
            ))}
            {pending > 0 ? <span className="h-5 rounded-sm border border-dashed border-line-2" /> : null}
          </div>
          {now ? (
            <p className="mt-2 text-sm">
              {t("Last 5 minutes:")} <span className="font-semibold">{t(RHYTHM[now].label)}</span> · {t(RHYTHM[now].why)}
              {before && before !== now ? (
                <span className="text-muted">
                  {" "}
                  ({t("before:")} {t(RHYTHM[before].label)})
                </span>
              ) : null}
            </p>
          ) : null}
          <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
            {(Object.keys(RHYTHM) as Rhythm[]).map((r) => (
              <li key={r} className="inline-flex items-center gap-1.5">
                <span className={cn("size-3 rounded-sm", RHYTHM[r].cls)} aria-hidden /> {t(RHYTHM[r].label)}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-muted-2">{t("Each window is ranked against the match so far: duels and turnovers near goal, pressing, and intensity.")}</p>
        </div>
      ) : null}
    </div>
  );
}

const MODELS: Record<string, string> = { pass_success: msg("Passes"), xg: msg("Shots (xG)") };
const AXIS = { fontSize: 11, fill: "var(--muted-2)", fontFamily: "var(--font-mono)" };

function CalibrationTab() {
  const t = useT();
  const [reports, setReports] = useState<CalibrationReport[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [model, setModel] = useState("pass_success");
  useEffect(() => {
    api.calibration().then(setReports, () => setFailed(true));
  }, []);
  if (failed) return <p className="text-sm text-muted">{t("Calibration isn't available right now.")}</p>;
  if (!reports) return <p className="text-sm text-muted">{t("Checking the engine against the match…")}</p>;
  const r = reports.find((x) => x.model === model) ?? reports[0];
  if (!r) return null;
  const data = r.bins.map((b) => ({ predicted: b.predicted * 100, observed: b.observed * 100, count: b.count }));
  return (
    <div>
      <p className="text-sm text-muted">
        {t("Does the engine's chance match what happened? Each dot is a group of similar attempts: predicted on the x-axis, how often it actually worked on the y-axis. Dots on the diagonal are well calibrated.")}
      </p>
      <ToggleGroup type="single" value={r.model} onValueChange={(v) => v && setModel(v)} aria-label={t("Passes or shots")} className="mt-3">
        {reports.map((x) => (
          <ToggleGroupItem key={x.model} value={x.model}>
            {t(MODELS[x.model] ?? x.model)}
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 8, bottom: 4, left: -4 }}>
            <CartesianGrid stroke="var(--line)" />
            <XAxis type="number" dataKey="predicted" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS} tickLine={false} axisLine={false} tickFormatter={(v: number) => `${v}%`} />
            <YAxis type="number" dataKey="observed" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={AXIS} tickLine={false} axisLine={false} width={44} tickFormatter={(v: number) => `${v}%`} />
            <ZAxis type="number" dataKey="count" range={[30, 260]} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="var(--muted-2)" strokeDasharray="4 4" />
            <ChartTooltip
              cursor={false}
              contentStyle={{ borderRadius: 12, border: "1px solid var(--line)", fontSize: 12 }}
              formatter={(v: number, name: string) => (name === "count" ? [String(v), t("attempts")] : [`${v.toFixed(0)}%`, name === "predicted" ? t("predicted") : t("happened")])}
            />
            <Scatter data={data} fill="var(--key)" fillOpacity={0.85} />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2">
        {[
          [String(r.samples), t("attempts checked")],
          [r.ece.toFixed(3), t("calibration error (ECE)")],
          [r.brier.toFixed(3), t("Brier score")],
        ].map(([v, l]) => (
          <div key={l} className="rounded-xl bg-panel-2 px-3 py-2">
            <dd className="num text-base">{v}</dd>
            <dt className="text-xs text-muted">{l}</dt>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-muted-2">{t("Lower is better for both. Scripted moments are left out.")}</p>
    </div>
  );
}

export function StatsDrawer({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const t = useT();
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent title={t("Match stats")} description={t("Every number here comes from the engine.")}>
        <Tabs defaultValue="team">
          <TabsList>
            <TabsTrigger value="team">{t("Team")}</TabsTrigger>
            <TabsTrigger value="players">{t("Workload")}</TabsTrigger>
            <TabsTrigger value="intensity">{t("Intensity")}</TabsTrigger>
            <TabsTrigger value="calibration">{t("Calibration")}</TabsTrigger>
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
          <TabsContent value="calibration">
            <CalibrationTab />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
