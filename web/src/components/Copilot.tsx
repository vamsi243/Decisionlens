import { HttpAgent } from "@ag-ui/client";
import {
  CopilotChat,
  CopilotKit,
  useAgentContext,
  useConfigureSuggestions,
  useRenderTool,
} from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import { Sparkles } from "lucide-react";
import { useMemo, type ReactNode } from "react";
import { z } from "zod";
import { API_URL } from "@/lib/api";
import { activeMoment } from "@/lib/moments";
import { cn } from "@/lib/utils";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";
import { useUi } from "@/state/ui";

/** The live page's CopilotKit provider, talking AG-UI straight to the stream service's /copilot. */
/** A random id per browser so each viewer's chat threads stay their own (no sign-in). */
function viewerId(): string {
  const key = "decision-lens-viewer";
  try {
    const have = localStorage.getItem(key);
    if (have) return have;
    const id = crypto.randomUUID();
    localStorage.setItem(key, id);
    return id;
  } catch {
    return crypto.randomUUID();
  }
}

export function CopilotProvider({ children }: { children: ReactNode }) {
  const agents = useMemo(
    () => ({ default: new HttpAgent({ url: `${API_URL}/copilot`, headers: { "X-Viewer-Id": viewerId() } }) }),
    [],
  );
  // No inspector: it adds a dev HUD that loads fonts and notices from third-party hosts.
  return (
    <CopilotKit selfManagedAgents={agents} enableInspector={false}>
      {children}
    </CopilotKit>
  );
}

interface MarkerRow {
  player_id: string;
  name: string;
  position: string;
  on_pitch: boolean;
  score_pct: number;
  aerial: number;
  ground: number;
  race: number;
  fatigue: number;
  reasons: string[];
}

interface Advice {
  attacker: { name: string; type: string };
  minute: number;
  channel: string;
  weights: Record<"aerial" | "ground" | "race", number>;
  options: MarkerRow[];
  excluded_names: string[];
}

const PARTS = [
  ["aerial", "bg-riv", "headers"],
  ["ground", "bg-[#eb6834]", "tackles"],
  ["race", "bg-green", "foot races"],
] as const;

/** The best_marker tool result as a ranked, stacked bar chart inside the chat. */
function MarkingChart({ advice }: { advice: Advice }) {
  return (
    <div className="dl-tokens my-2 rounded-xl border border-line bg-surface p-3.5 text-ink">
      <p className="text-xs text-muted">
        Marking {advice.attacker.name} ({advice.attacker.type}) · {advice.minute}' · plays down the {advice.channel}
        {advice.excluded_names.length ? ` · ruled out: ${advice.excluded_names.join(", ")}` : ""}
      </p>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-muted">
        {PARTS.map(([k, c, label]) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className={cn("size-2.5 rounded-sm", c)} />
            {label} {Math.round(advice.weights[k] * 100)}%
          </span>
        ))}
      </div>
      <ol className="mt-3 space-y-2.5">
        {advice.options.map((o, i) => (
          <li key={o.player_id}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className={cn(i === 0 && "font-semibold")}>
                {i + 1}. {o.name} <span className="text-xs text-muted">· {o.position}{o.on_pitch ? "" : " · bench"}</span>
              </span>
              <span className="num text-sm">{o.score_pct}%</span>
            </div>
            <div className="mt-1 flex h-2.5 overflow-hidden rounded-full bg-panel-2" aria-hidden>
              {PARTS.map(([k, c]) => (
                <span key={k} className={c} style={{ width: `${advice.weights[k] * o[k] * 100}%` }} />
              ))}
            </div>
            {o.reasons.length ? <p className="mt-1 text-[11px] text-muted">{o.reasons.join(" · ")}</p> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

function parse<T>(result: unknown): T | null {
  if (!result) return null;
  try {
    return (typeof result === "string" ? JSON.parse(result) : result) as T;
  } catch {
    return null;
  }
}

/** Chat docked under the board: quick questions about the live match, answered from the engine. */
function MatchCopilotInner() {
  // Minute-level selectors: the board ticks at 10 Hz, the chat context shouldn't.
  const minute = useMatch((s) => Math.floor(s.clockMs / 60_000) + 1);
  const momentTitle = useMatch(
    (s) => activeMoment(s.seen, s.analyses, s.clockMs, s.pinned)?.moment.title ?? null,
  );
  const meta = useMatch((s) => s.meta);
  const stats = useMatch((s) => s.stats);
  const players = useMatch((s) => s.players);
  const persona = usePrefs((s) => s.persona);
  const followed = usePrefs((s) => s.player);
  const panel = useUi((s) => s.panel);
  const goals = (stats?.teams ?? []).map((t) => `${t.team_id}:${t.goals}`).join(",");

  // What the viewer is looking at, so answers follow the screen.
  const context = useMemo(
    () => ({
      description: "What the viewer is looking at on the live board",
      value: {
        minute,
        score: Object.fromEntries(
          goals
            .split(",")
            .filter(Boolean)
            .map((g) => {
              const [id, n] = g.split(":");
              return [meta?.teams.find((m) => m.team_id === id)?.name ?? id, Number(n)];
            }),
        ),
        viewer: persona === "fan" ? "fan: plain words, at most two numbers" : "analyst",
        following: followed ? players[followed]?.name ?? null : null,
        player_panel_open_for: panel ? players[panel]?.name ?? null : null,
        key_moment_on_screen: momentTitle,
      },
    }),
    [minute, goals, meta, persona, followed, panel, players, momentTitle],
  );
  useAgentContext(context);

  useConfigureSuggestions(
    {
      suggestions:
        persona === "fan"
          ? [
              { title: "Who's been the best?", message: "Who has been the best player so far, and why?" },
              { title: "Why did Pell lose that?", message: "Why did Jonah Pell lose the header to Dax Morrow?" },
              { title: "Who's out of puff?", message: "Who is the most tired player right now?" },
              { title: "Who should mark Morrow?", message: "Who should mark Dax Morrow right now?" },
            ]
          : [
              { title: "Who should mark Morrow?", message: "Who should mark Dax Morrow right now?" },
              { title: "Who's tiring?", message: "Who is most tired, and who on the bench could replace them?" },
              { title: "Reyes-Ward's passing", message: "How many passes has Callum Reyes-Ward completed?" },
              { title: "Kollmann's big calls", message: "What were Ezra Kollmann's key decisions?" },
            ],
      available: "always",
    },
    [persona],
  );

  useRenderTool(
    {
      name: "best_marker",
      parameters: z.object({ attacker: z.string(), exclude: z.array(z.string()).nullish() }),
      render: ({ status, parameters, result }) => {
        const advice = parse<Advice>(result);
        if (status !== "complete" || !advice) {
          return (
            <p className="my-2 text-xs text-muted">Scoring every possible marker for {parameters?.attacker ?? "…"}…</p>
          );
        }
        return <MarkingChart advice={advice} />;
      },
    },
    [],
  );

  return (
    <section aria-label="Match copilot" className="mt-6 overflow-hidden rounded-2xl border border-line bg-surface shadow-sm">
      <header className="flex items-center gap-2 border-b border-line px-4 py-3">
        <span className="grid size-7 place-items-center rounded-lg bg-chrome text-white">
          <Sparkles className="size-3.5" aria-hidden />
        </span>
        <div>
          <h2 className="font-display text-sm font-semibold tracking-tight">Match copilot</h2>
          <p className="text-xs text-muted">Ask about any player or matchup. Every number comes from the engine.</p>
        </div>
      </header>
      <div className="copilot-chat h-[460px]">
        <CopilotChat agentId="default" />
      </div>
    </section>
  );
}

/** The copilot with its own CopilotKit provider: lazy-loaded so other pages don't ship it. */
export default function MatchCopilot() {
  return (
    <CopilotProvider>
      <MatchCopilotInner />
    </CopilotProvider>
  );
}
