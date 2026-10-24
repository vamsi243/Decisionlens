import { ArrowDown, Flag } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { Overlay, Persona } from "@/types/contracts";
import { useEffect, useMemo, useRef, useState } from "react";
import { minute } from "@/lib/format";
import { activeMoment, MOMENT_LABEL } from "@/lib/moments";
import {
  ensureAnalyses,
  ensureTranslations,
  revealedMoments,
  useMatch,
} from "@/state/match";
import { useT } from "@/lib/i18n";
import { sfx } from "@/lib/sfx";
import { useTr } from "@/lib/tr";
import { usePrefs } from "@/state/prefs";
import { PlayersToWatch } from "./fan/FanOverlays";
import { MomentCard, narration, SourceBadge } from "./MomentCard";
import { replayMoment } from "./Scrubber";
import { Button } from "./ui/button";
import { ToggleGroup, ToggleGroupItem } from "./ui/toggle-group";

function RecapCard({
  overlay,
  persona,
  lang,
}: {
  overlay: Overlay;
  persona: Persona;
  lang: string;
}) {
  const reduce = useReducedMotion();
  const tr = useTr();
  const title = tr(String(overlay.payload?.title ?? "Recap"));
  return (
    <motion.article
      initial={reduce ? false : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-lg border border-ink/15 bg-ink p-4 text-surface shadow-md"
    >
      <header className="flex items-center gap-2 text-xs text-surface/60">
        <Flag className="size-3.5" aria-hidden />
        <span className="font-medium uppercase tracking-wide">{title}</span>
      </header>
      <p
        className={
          persona === "fan"
            ? "mt-2 text-base leading-snug"
            : "mt-2 text-sm leading-relaxed"
        }
      >
        {narration(overlay, persona, lang)}
      </p>
      <footer className="mt-3 flex justify-end opacity-70">
        <SourceBadge overlay={overlay} />
      </footer>
    </motion.article>
  );
}

export function MomentFeed() {
  const seen = useMatch((s) => s.seen);
  const allMoments = useMatch((s) => s.allMoments);
  const clockMs = useMatch((s) => s.clockMs);
  const analyses = useMatch((s) => s.analyses);
  const players = useMatch((s) => s.players);
  const workload = useMatch((s) => s.workload);
  const pinned = useMatch((s) => s.pinned);
  const overlays = useMatch((s) => s.overlays);
  const noTranslation = useMatch((s) => s.noTranslation);
  const persona = usePrefs((s) => s.persona);
  const lang = usePrefs((s) => s.language);
  const favPlayer = usePrefs((s) => s.player);
  const favClub = usePrefs((s) => s.club);
  const meta = useMatch((s) => s.meta);
  const [scope, setScope] = useState<"all" | "club">("all");
  const t = useT();
  const clubName = meta?.teams.find((t) => t.team_id === favClub)?.name;

  const moments = useMemo(
    () => revealedMoments({ seen, allMoments, clockMs }),
    [seen, allMoments, clockMs],
  );
  useEffect(() => ensureAnalyses(moments), [moments]);
  const recaps = useMemo(
    () =>
      Object.values(overlays).filter(
        (o) => o.kind === "recap" && o.t_ms <= clockMs,
      ),
    [overlays, clockMs],
  );
  const inScope = useMemo(
    () =>
      scope === "club" && favClub
        ? moments.filter((m) => m.team_id === favClub)
        : moments,
    [moments, scope, favClub],
  );
  // The followed player's moments come first: a compact strip above the timeline.
  const mine = useMemo(
    () =>
      favPlayer ? moments.filter((m) => m.players.includes(favPlayer)) : [],
    [moments, favPlayer],
  );
  const items = useMemo(
    () =>
      [
        ...inScope.map((m) => ({
          t: m.t_ms,
          key: m.moment_id,
          moment: m,
          recap: undefined,
        })),
        ...recaps.map((o) => ({
          t: o.t_ms,
          key: o.overlay_id,
          moment: undefined,
          recap: o,
        })),
      ].sort((a, b) => a.t - b.t),
    [inScope, recaps],
  );
  const cardIds = items
    .map((i) => (i.recap ? i.recap.overlay_id : `ov_${i.key}`))
    .join();
  useEffect(() => {
    ensureTranslations(cardIds ? cardIds.split(",") : [], lang);
  }, [cardIds, lang, overlays]);
  const active = activeMoment(seen, analyses, clockMs, pinned)?.moment
    .moment_id;

  const box = useRef<HTMLDivElement>(null);
  // A soft tick as each card scrolls into view while *you* scroll (the feed or the page), never
  // during the feed's own auto-scroll.
  useEffect(() => {
    let user = 0;
    const mark = () => {
      user = performance.now();
    };
    const opts = { passive: true } as const;
    window.addEventListener("wheel", mark, opts);
    window.addEventListener("touchmove", mark, opts);
    window.addEventListener("keydown", mark);
    const io = new IntersectionObserver(
      (entries) => {
        if (performance.now() - user > 700) return;
        if (entries.some((e) => e.isIntersecting)) sfx.tick();
      },
      { threshold: 0.25 },
    );
    box.current?.querySelectorAll("article").forEach((a) => io.observe(a));
    return () => {
      io.disconnect();
      window.removeEventListener("wheel", mark);
      window.removeEventListener("touchmove", mark);
      window.removeEventListener("keydown", mark);
    };
  }, [items.length]);
  const [follow, setFollow] = useState(true);
  useEffect(() => {
    if (follow && box.current)
      box.current.scrollTo({
        top: box.current.scrollHeight,
        behavior: "smooth",
      });
  }, [items.length, follow]);

  return (
    <section
      className="relative flex min-h-0 flex-col"
      aria-label="Key moments"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h2 className="font-display text-sm font-semibold tracking-tight">
            {persona === "fan" ? t("Big moments") : t("Key moments")}
          </h2>
          {clubName ? (
            <ToggleGroup
              type="single"
              value={scope}
              onValueChange={(v) => v && setScope(v as "all" | "club")}
              aria-label={t("Which moments")}
            >
              <ToggleGroupItem value="all">{t("All")}</ToggleGroupItem>
              <ToggleGroupItem value="club">{clubName}</ToggleGroupItem>
            </ToggleGroup>
          ) : null}
        </div>
        <span className="flex items-center gap-2 text-xs text-muted-2">
          {noTranslation && lang !== "en" ? (
            <span>{t("English only (no Translator key)")}</span>
          ) : null}
          <span className="num">{inScope.length}</span>
        </span>
      </div>
      <div
        ref={box}
        onScroll={(e) => {
          const el = e.currentTarget;
          setFollow(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
        }}
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto pb-2 pr-1"
      >
        {persona === "fan" ? <PlayersToWatch /> : null}
        {favPlayer && players[favPlayer] && persona !== "fan" ? (
          <div className="rounded-lg border border-amber/40 bg-amber/5 p-3">
            <p className="text-xs font-medium text-amber">
              {mine.length === 1
                ? t("Following {name} · 1 moment", {
                    name: players[favPlayer]!.name,
                  })
                : t("Following {name} · {n} moments", {
                    name: players[favPlayer]!.name,
                    n: mine.length,
                  })}
            </p>
            {mine.length ? (
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {mine.map((m) => (
                  <li key={m.moment_id}>
                    <button
                      type="button"
                      onClick={() => void replayMoment(m)}
                      className="rounded-full border border-line bg-surface px-2.5 py-1 text-xs hover:bg-panel-2"
                    >
                      <span className="num text-amber">{minute(m.t_ms)}</span>{" "}
                      {t(MOMENT_LABEL[m.type])}
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-1 text-xs text-muted">
                {t("No key moments for them yet.")}
              </p>
            )}
          </div>
        ) : null}
        {moments.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-2 p-4 text-sm text-muted">
            {t("Moments worth explaining appear here as the match plays.")}
          </p>
        ) : null}
        <AnimatePresence initial={false}>
          {items.map(({ key, moment: m, recap }) =>
            recap ? (
              <RecapCard
                key={key}
                overlay={recap}
                persona={persona}
                lang={lang}
              />
            ) : m ? (
              <MomentCard
                key={key}
                moment={m}
                analysis={analyses[m.moment_id]}
                overlay={overlays[`ov_${m.moment_id}`]}
                lang={lang}
                persona={persona}
                players={players}
                workload={workload}
                active={m.moment_id === active}
                favourite={
                  (favPlayer !== null && m.players.includes(favPlayer)) ||
                  (favClub !== null && m.team_id === favClub)
                }
              />
            ) : null,
          )}
        </AnimatePresence>
      </div>
      {!follow ? (
        <Button
          size="sm"
          variant="primary"
          className="absolute bottom-4 left-1/2 -translate-x-1/2 shadow-lg"
          onClick={() => setFollow(true)}
        >
          <ArrowDown className="size-3.5" /> {t("Jump to live")}
        </Button>
      ) : null}
    </section>
  );
}
