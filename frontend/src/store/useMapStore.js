import { create } from 'zustand';

export const useMapStore = create((set) => ({
  viewport: { center: [12.9716, 77.5946], zoom: 12 }, // Bangalore center
  activeFilters: {
    incidents: true,
    corridors: true,
    blackspots: false,
    surge: false,
  },
  setViewport: (viewport) => set({ viewport }),
  toggleFilter: (filterName) => set((state) => ({
    activeFilters: { ...state.activeFilters, [filterName]: !state.activeFilters[filterName] }
  })),
}));
