import { useCallback, useSyncExternalStore } from "react";
import { api } from "@/lib/api";
import { useMatch } from "@/state/match";
import { usePrefs } from "@/state/prefs";

/**
 * Engine text in the viewer's language: moment titles, bullets, commentary, banners, recap
 * bullets, player-panel lines, the copilot's chart reasons. Strings are batched (one request
 * every 60 ms), translated server-side by Azure AI Translator and cached on both sides, so a
 * repeated phrase costs nothing. Until a translation arrives the English shows, then swaps in.
 */

const cache = new Map<string, string>(); // `${lang}\u0000${text}` -> translation
const pending = new Map<string, Set<string>>(); // lang -> texts to ask for
const inflight = new Set<string>();
const unavailable = new Set<string>(); // languages the server can't translate (no key)
const listeners = new Set<() => void>();
let version = 0;
let timer: ReturnType<typeof setTimeout> | undefined;

const key = (lang: string, text: string) => `${lang}\u0000${text}`;

function notify() {
  version += 1;
  listeners.forEach((l) => l());
}

async function flush() {
  timer = undefined;
  const jobs = [...pending.entries()];
  pending.clear();
  for (const [lang, set] of jobs) {
    const texts = [...set];
    for (let i = 0; i < texts.length; i += 100) {
      const chunk = texts.slice(i, i + 100);
      try {
        const res = await api.translate(lang, chunk);
        chunk.forEach((t, j) => cache.set(key(lang, t), res.texts[j] ?? t));
      } catch (e) {
        if ((e as Error).message.endsWith("503")) {
          unavailable.add(lang);
          useMatch.getState().setNoTranslation(true);
        }
      } finally {
        chunk.forEach((t) => inflight.delete(key(lang, t)));
      }
    }
  }
  notify();
}

function request(lang: string, text: string) {
  const k = key(lang, text);
  if (inflight.has(k) || unavailable.has(lang)) return;
  inflight.add(k);
  const set = pending.get(lang) ?? new Set<string>();
  set.add(text);
  pending.set(lang, set);
  timer ??= setTimeout(() => void flush(), 60);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

/** `tr(text)` → the cached translation, or the English while one is fetched. */
export function useTr(): (text: string | null | undefined) => string {
  const lang = usePrefs((s) => s.language);
  const v = useSyncExternalStore(subscribe, () => version);
  return useCallback(
    (text: string | null | undefined) => {
      if (!text) return text ?? "";
      if (lang === "en") return text;
      const hit = cache.get(key(lang, text));
      if (hit !== undefined) return hit;
      request(lang, text);
      return text;
    },
    // `v` re-creates the function when translations land, so callers re-render with them
    [lang, v],
  );
}
