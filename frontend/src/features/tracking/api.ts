import { all, api } from "../../shared/apiClient";
import type { Entry } from "../../shared/types";
export const trackingApi = {
  current: () => api<{ entry: Entry | null; server_time: string }>("/timer"),
  entries: () => all<Entry>("/time"),
  start: (body: unknown) => api<Entry>("/timer", "POST", body),
  command: (id: string, command: string) =>
    api<Entry>(`/timer/${id}/${command}`, "POST"),
  adjust: (id: string, body: unknown) =>
    api<Entry>(`/time/${id}`, "PATCH", body),
};
