import { create } from "zustand";

interface SelectionStore {
  selected: Set<string>;

  toggleSelect: (id: string) => void;

  clearSelection: () => void;

  selectAll: (ids: string[]) => void;
}

export const useSelectionStore =
  create<SelectionStore>((set) => ({
    selected: new Set(),

    toggleSelect: (id) =>
      set((state) => {
        const next = new Set(state.selected);

        if (next.has(id)) {
          next.delete(id);
        } else {
          next.add(id);
        }

        return { selected: next };
      }),

    clearSelection: () =>
      set({
        selected: new Set(),
      }),

    selectAll: (ids) =>
      set({
        selected: new Set(ids),
      }),
      
  }));