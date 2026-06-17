import { client } from "./client";

export const predictTriage = async (data) => {
  const response = await client.post("/predict/triage", data);
  return response.data;
};

export const predictCascade = async (data) => {
  const response = await client.post("/predict/cascade", data);
  return response.data;
};
