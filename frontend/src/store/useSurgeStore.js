import { create } from 'zustand';
import { getSurgeVulnerability, getSurgeReplay } from '../api/surge';

export const useSurgeStore = create((set) => ({
  vulnerability: null,
  replayData: null,
  activeHour: 5,
  loading: false,
  error: null,

  fetchSurgeData: async () => {
    set({ loading: true, error: null });
    try {
      const [vuln, replay] = await Promise.all([
        getSurgeVulnerability().catch(() => null),
        getSurgeReplay().catch(() => null)
      ]);
      set({ vulnerability: vuln, replayData: replay, loading: false });
    } catch (err) {
      set({ error: err.message, loading: false });
    }
  },

  setActiveHour: (hour) => set({ activeHour: hour }),
}));
