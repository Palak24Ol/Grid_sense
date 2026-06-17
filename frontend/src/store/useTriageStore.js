import { create } from 'zustand';
import { predictTriage, predictCascade } from '../api/predict';

export const useTriageStore = create((set, get) => ({
  formData: {
    event_type: 'unplanned', // 'unplanned' | 'planned'
    event_cause: 'vehicle_breakdown',
    corridor: 'Hosur Road',
    vehicle_type: 'none',
    hour_of_day: 18,
    day_of_week: 1, // 0 = Mon, 6 = Sun
  },
  loading: false,
  error: null,
  triageResult: null,
  cascadeResult: null,

  setFormData: (updates) => set((state) => ({
    formData: { ...state.formData, ...updates },
    // Clear results if form data changes
    triageResult: null,
    cascadeResult: null,
    error: null,
  })),

  submitPrediction: async () => {
    const { formData } = get();
    set({ loading: true, error: null, triageResult: null, cascadeResult: null });

    try {
      if (formData.event_type === 'unplanned') {
        // Drop event_type before sending to ML API if not needed, or let backend ignore it
        const res = await predictTriage({
          event_cause: formData.event_cause,
          corridor: formData.corridor,
          vehicle_type: formData.vehicle_type,
          hour_of_day: Number(formData.hour_of_day),
          day_of_week: Number(formData.day_of_week),
        });
        set({ triageResult: res, loading: false });
      } else {
        const res = await predictCascade({
          event_cause: formData.event_cause,
          corridor: formData.corridor,
          hour_of_day: Number(formData.hour_of_day),
          day_of_week: Number(formData.day_of_week),
        });
        set({ cascadeResult: res, loading: false });
      }
    } catch (err) {
      set({ error: err.message || 'Prediction failed', loading: false });
    }
  },

  reset: () => set({ triageResult: null, cascadeResult: null, error: null }),
}));
