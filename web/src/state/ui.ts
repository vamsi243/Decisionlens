import { create } from "zustand";
import { sfx } from "@/lib/sfx";

/** Transient UI state shared across components (not saved): which player's panel is open. */
interface Ui {
  panel: string | null;
  openPanel: (playerId: string | null) => void;
}

export const useUi = create<Ui>()((set) => ({
  panel: null,
  openPanel: (panel) =>
    set((s) => {
      if (panel && panel !== s.panel) sfx.open();
      if (!panel && s.panel) sfx.close();
      return { panel };
    }),
}));
