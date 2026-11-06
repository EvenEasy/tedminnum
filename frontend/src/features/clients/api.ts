import { all, api } from "../../shared/apiClient";
import type { Client } from "../../shared/types";
export const clientApi = {
  list: () => all<Client>("/clients"),
  save: (id: string | undefined, body: unknown) =>
    api<Client>(
      id ? `/clients/${id}` : "/clients",
      id ? "PATCH" : "POST",
      body,
    ),
};
