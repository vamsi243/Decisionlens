import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { Persona } from "@/types/contracts";

export type WhatIfProfile = "auto" | "fresh_sub" | "archetype";

export interface Prefs {
  persona: Persona;
  club: string | null; // favourite club id
  player: string | null; // analyst mode: favourite player id
  follow: string | null; // fan mode: the player you follow (kept apart, so it never leaks into analyst mode)
  language: string;
  whatIf: WhatIfProfile;
  pauseAtMoments: boolean;
  boardSize: number; // live page: pitch width, % of the workspace
  followCam: boolean; // fan mode: the pitch follows the followed player
  sound: boolean; // quiet UI sounds
  set: (p: Partial<Omit<Prefs, "set">>) => void;
}

/** localStorage can throw (private mode, blocked storage): fall back to memory. */
const memory = new Map<string, string>();
const safeStorage: StateStorage = {
  getItem: (k) => {
    try {
      return localStorage.getItem(k);
    } catch {
      return memory.get(k) ?? null;
    }
  },
  setItem: (k, v) => {
    try {
      localStorage.setItem(k, v);
    } catch {
      memory.set(k, v);
    }
  },
  removeItem: (k) => {
    try {
      localStorage.removeItem(k);
    } catch {
      memory.delete(k);
    }
  },
};

export const usePrefs = create<Prefs>()(
  persist(
    (set) => ({
      persona: "analyst",
      club: null,
      player: null,
      follow: null,
      language: "en",
      whatIf: "auto",
      pauseAtMoments: true,
      boardSize: 64,
      followCam: true,
      sound: true,
      set: (p) => set(p),
    }),
    {
      name: "decision-lens-prefs",
      storage: createJSONStorage(() => safeStorage),
      // v1 split the fan follow from the analyst favourite. Before that the one `player` was
      // mostly set by tapping players in fan mode, so it becomes the fan follow.
      version: 1,
      migrate: (old, from) => {
        const s = (old ?? {}) as Partial<Prefs>;
        return from < 1 ? { ...s, follow: s.player ?? null, player: null } : s;
      },
    },
  ),
);

/** The highlighted player for the current persona: fans follow one, analysts keep a favourite. */
export function useFocus(): string | null {
  return usePrefs((s) => (s.persona === "fan" ? s.follow : s.player));
}

/** The prefs change that sets (or clears) the highlighted player for a persona. */
export function focusPatch(persona: Persona, id: string | null): Partial<Omit<Prefs, "set">> {
  return persona === "fan" ? { follow: id } : { player: id };
}

export const LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "pt", label: "Português" },
  { code: "de", label: "Deutsch" },
  { code: "hi", label: "हिन्दी" },
];
