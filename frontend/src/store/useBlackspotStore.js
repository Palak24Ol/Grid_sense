import { create } from 'zustand';
import { getBlackspotJunctions, getNeglectIndex, getJunctionProfile } from '../api/blackspot';

export const useBlackspotStore = create((set, get) => ({
  blackspots: [],
  chronicCount: 0,
  criticalCount: 0,
  neglectIndex: [],
  selectedJunction: null,
  activeTierFilter: 'All',
  loading: false,
  error: null,

  fetchBlackspots: async (filters = {}) => {
    set({ loading: true, error: null });
    try {
      const data = await getBlackspotJunctions(filters);
      set({ 
        blackspots: data.junctions || [],
        chronicCount: data.chronic_count || 0,
        criticalCount: data.critical_count || 0,
        loading: false 
      });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },

  fetchNeglectIndex: async () => {
    try {
      const data = await getNeglectIndex();
      set({ neglectIndex: data.stations || [] });
    } catch (err) {
      console.error(err);
    }
  },

  selectJunction: async (junction) => {
    set({ loading: true, error: null });
    try {
      // Typically would fetch profile, but since we have full junction details in blackspots array,
      // we can just use that, or simulate fetching.
      const match = get().blackspots.find(b => b.junction === junction);
      if (match) {
        set({ selectedJunction: match, loading: false });
      } else {
        const data = await getJunctionProfile(junction);
        set({ selectedJunction: data, loading: false });
      }
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },

  setTierFilter: (tier) => {
    set({ activeTierFilter: tier });
    get().fetchBlackspots(tier !== 'All' ? { tier } : {});
  },

  clearSelection: () => set({ selectedJunction: null }),
}));
