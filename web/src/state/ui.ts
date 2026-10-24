import { create } from "zustand";

/** Transient UI state shared across components (not saved): which player's panel is open. */
interface Ui {
  panel: string | null;
  openPanel: (playerId: string | null) => void;
}

export const useUi = create<Ui>()((set) => ({
  panel: null,
  openPanel: (panel) => set({ panel }),
}));
