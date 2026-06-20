import { client } from "./client";
import mockData from "./mocks/incidents.json";

// Mock mode is opt-out: default to mock (safe placeholder data) unless the
// dev explicitly sets VITE_USE_MOCK=false. VITE_API_BASE_URL is a separate,
// optional concern — it only overrides the backend URL (see client.js,
// which already falls back to http://localhost:8000/api/v1) and should
// never gate whether mock data is used.
const USE_MOCK = import.meta.env.VITE_USE_MOCK !== "false";

export const getIncidents = async (filters = {}) => {
  if (USE_MOCK) {
    return mockData;
  }
  // Fetch from real backend — cap at 300, exclude stale
  const response = await client.get("/incidents", {
    params: { exclude_stale: true, limit: 300, ...filters },
  });

  const data = response.data;
  const all = Array.isArray(data) ? data : (data.incidents || []);

  // Filter to active only + valid Bengaluru coordinates
  const active = all.filter(
    (i) =>
      i.status === "active" &&
      i.latitude >= 12.75 && i.latitude <= 13.20 &&
      i.longitude >= 77.35 && i.longitude <= 77.80
  );

  return { total: active.length, filtered: active.length, incidents: active };
};

export const getIncidentSummary = async () => {
  if (USE_MOCK) {
    const { incidents } = mockData;
    return {
      total:    incidents.length,
      high:     incidents.filter(i => i.priority === "High").length,
      low:      incidents.filter(i => i.priority === "Low").length,
      closures: incidents.filter(i => i.requires_road_closure).length,
    };
  }
  const response = await client.get("/incidents/summary");
  return response.data;
};
