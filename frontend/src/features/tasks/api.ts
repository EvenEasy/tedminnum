import { all, api } from "../../shared/apiClient";
import type { Task } from "../../shared/types";
export const taskApi = {
  list: () => all<Task>("/tasks"),
  save: (id: string | undefined, body: unknown) =>
    api<Task>(id ? `/tasks/${id}` : "/tasks", id ? "PATCH" : "POST", body),
  update: (id: string, body: unknown) =>
    api<Task>(`/tasks/${id}`, "PATCH", body),
  move: (id: string, body: { version: number; direction: "up" | "down" }) =>
    api<Task>(`/tasks/${id}/move`, "POST", body),
};
