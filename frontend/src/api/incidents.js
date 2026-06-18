import { client } from "./client";
import mockIncidents from "./mocks/incidents.json";

const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true" || !import.meta.env.VITE_API_BASE_URL;

export const getIncidents = async (filters = {}) => {
  if (USE_MOCK) {
    return mockIncidents;
  }
  const response = await client.get("/incidents", { params: filters });
  return response.data;
};

export const getIncidentSummary = async () => {
  if (USE_MOCK) {
    const { incidents } = mockIncidents;
    return {
      total: incidents.length,
      high: incidents.filter(i => i.priority === "High").length,
      medium: incidents.filter(i => i.priority === "Medium").length,
      low: incidents.filter(i => i.priority === "Low").length,
      closures: incidents.filter(i => i.requires_road_closure).length,
    };
  }
  const response = await client.get("/incidents/summary");
  return response.data;
};
