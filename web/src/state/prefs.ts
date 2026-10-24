import { create } from "zustand";
import { createJSONStorage, persist, type StateStorage } from "zustand/middleware";
import type { Persona } from "@/types/contracts";

export type WhatIfProfile = "auto" | "fresh_sub" | "archetype";

interface Prefs {
  persona: Persona;
  club: string | null; // favourite club id
  player: string | null; // favourite player id
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
      language: "en",
      whatIf: "auto",
      pauseAtMoments: true,
      boardSize: 64,
      followCam: true,
      sound: true,
      set: (p) => set(p),
    }),
    { name: "decision-lens-prefs", storage: createJSONStorage(() => safeStorage) },
  ),
);

export const LANGUAGES: { code: string; label: string }[] = [
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "pt", label: "Português" },
  { code: "de", label: "Deutsch" },
  { code: "hi", label: "हिन्दी" },
];
