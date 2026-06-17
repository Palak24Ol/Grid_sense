import { client } from "./client";

export const getSurgeVulnerability = async () => {
  const response = await client.get("/surge/vulnerability");
  return response.data;
};

export const getSurgeReplay = async () => {
  const response = await client.get("/surge/replay/march7");
  return response.data;
};
