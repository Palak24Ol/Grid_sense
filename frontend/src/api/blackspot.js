import { client } from "./client";

export const getBlackspotJunctions = async (filters = {}) => {
  const response = await client.get("/blackspot/junctions", { params: filters });
  return response.data;
};

export const getNeglectIndex = async () => {
  const response = await client.get("/blackspot/neglect");
  return response.data;
};

export const getJunctionProfile = async (junction) => {
  const response = await client.get(`/blackspot/junctions/${encodeURIComponent(junction)}`);
  return response.data;
};
