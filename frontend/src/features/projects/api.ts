import { all, api } from "../../shared/apiClient";
import type { Project } from "../../shared/types";
export const projectApi = {
  list: () => all<Project>("/projects"),
  save: (id: string | undefined, body: unknown) =>
    api<Project>(
      id ? `/projects/${id}` : "/projects",
      id ? "PATCH" : "POST",
      body,
    ),
};
