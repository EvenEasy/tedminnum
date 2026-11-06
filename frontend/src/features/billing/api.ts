import { all, api } from "../../shared/apiClient";
import type { Invoice } from "../../shared/types";
export const billingApi = {
  list: () => all<Invoice>("/invoices"),
  invoice: (id: string) => api<Invoice>(`/invoices/${id}`),
  draft: (body: unknown) => api<Invoice>("/invoices", "POST", body),
  transition: (id: string, command: "issue" | "void") =>
    api<Invoice>(`/invoices/${id}/${command}`, "POST"),
  describe: (id: string, lineId: string, body: { description: string }) =>
    api(`/invoices/${id}/lines/${lineId}`, "PATCH", body),
  payment: (id: string, body: unknown) =>
    api(`/payments?invoice_id=${id}`, "POST", body),
};
