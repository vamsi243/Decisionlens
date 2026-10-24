import { useEffect, useState } from "react";
import { Activity } from "lucide-react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function App() {
  const [status, setStatus] = useState<string>("connecting…");

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((r) => r.json())
      .then((d: { status: string; run_mode: string }) => setStatus(`${d.status} · ${d.run_mode}`))
      .catch(() => setStatus("api offline"));
  }, []);

  return (
    <main className="min-h-screen bg-bg px-4 py-10 sm:px-10">
      <div className="mx-auto max-w-5xl">
        <header className="flex items-center justify-between">
          <h1 className="font-display text-2xl font-semibold tracking-tight">Decision Lens</h1>
          <span className="num flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-1.5 text-sm text-muted shadow-sm">
            <Activity className="size-4 text-green" aria-hidden />
            {status}
          </span>
        </header>

        <section className="mt-8 rounded-xl border border-line bg-surface p-6 shadow-lg">
          <p className="text-muted">Every moment, every option, every fan.</p>
          <div className="mt-6 aspect-[105/68] w-full rounded-xl border border-line bg-panel-2" />
          <div className="mt-6 flex flex-wrap gap-3">
            <Chip label="Riverside FC" value="0" />
            <Chip label="Hillton United" value="0" />
            <Chip label="Clock" value="00:00" accent />
          </div>
        </section>
      </div>
    </main>
  );
}

function Chip({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-2 shadow-sm">
      <span className="text-sm text-muted">{label}</span>
      <span className={`num text-sm font-medium ${accent ? "text-amber" : "text-ink"}`}>{value}</span>
    </div>
  );
}
