import { all, api } from "../../shared/apiClient";
import type {
  Audit,
  Delivery,
  Hook,
  User,
  Workspace,
} from "../../shared/types";
export const settingsApi = {
  get: () => api<{ workspace: Workspace }>("/settings"),
  preferences: (body: unknown) =>
    api<User>("/settings/preferences", "PATCH", body),
  workspace: (body: unknown) =>
    api<Workspace>("/settings/workspace", "PATCH", body),
  users: () => all<User>("/users"),
  createUser: (body: unknown) => api<User>("/users", "POST", body),
  updateUser: (id: string, body: unknown) =>
    api<User>(`/users/${id}`, "PATCH", body),
  audit: () => all<Audit>("/audit"),
  hooks: () => api<{ items: Hook[]; deliveries: Delivery[] }>("/webhooks"),
  createHook: (body: unknown) =>
    api<Hook & { secret: string }>("/webhooks", "POST", body),
  toggleHook: (id: string, enabled: boolean) =>
    api<Hook>(`/webhooks/${id}`, "PATCH", { enabled }),
  rotateHook: (id: string, enabled: boolean) =>
    api<Hook & { secret: string }>(`/webhooks/${id}`, "PATCH", {
      enabled,
      rotate_secret: true,
    }),
};
