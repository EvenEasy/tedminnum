import { api } from "../../shared/apiClient";
import type { Dashboard } from "../../shared/types";
export const dashboardApi = {
  summary: (day: string) =>
    api<Dashboard>("/dashboard?day_start=" + encodeURIComponent(day)),
};
