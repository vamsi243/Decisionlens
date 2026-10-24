import { useCallback } from "react";
import de from "@/i18n/de.json";
import es from "@/i18n/es.json";
import fr from "@/i18n/fr.json";
import hi from "@/i18n/hi.json";
import pt from "@/i18n/pt.json";
import { usePrefs } from "@/state/prefs";

/**
 * Fixed UI wording in the viewer's language. The English text is the key: write
 * `t("Key moments")` or `t("Following · {km}", { km })`, and wrap literals defined elsewhere
 * in `msg("…")`. `scripts/i18n_strings.py` finds every such literal, machine-translates it
 * once with Azure AI Translator and writes `src/i18n/<lang>.json`; anything missing falls
 * back to English. Engine text that changes with the match goes through `lib/tr.ts` instead.
 */

type Dict = Record<string, string>;
const DICTS: Record<string, Dict> = { de, es, fr, hi, pt };

export type Params = Record<string, string | number>;

/** Marks an English literal for extraction without translating it here (e.g. a label table). */
export const msg = (s: string) => s;

export function translate(lang: string, text: string, params?: Params): string {
  const out = (lang !== "en" && DICTS[lang]?.[text]) || text;
  return params ? out.replace(/\{(\w+)\}/g, (m, k: string) => (k in params ? String(params[k]) : m)) : out;
}

export function useT(): (text: string, params?: Params) => string {
  const lang = usePrefs((s) => s.language);
  return useCallback((text: string, params?: Params) => translate(lang, text, params), [lang]);
}
