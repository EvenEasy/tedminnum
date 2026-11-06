import { api } from "../../shared/apiClient";
import type { User } from "../../shared/types";
export const authApi = {
  login: (email: string, password: string) =>
    api<{ user: User; csrf: string }>("/auth/login", "POST", {
      email,
      password,
    }),
  me: (signal?: AbortSignal) =>
    api<{ user: User; csrf: string }>("/auth/me", "GET", undefined, { signal }),
  logout: () => api("/auth/logout", "POST"),
  password: (body: unknown) => api("/auth/password", "POST", body),
};
