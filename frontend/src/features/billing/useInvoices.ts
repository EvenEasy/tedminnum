import { useRef, useState } from "react";
import { uid } from "../../shared/apiClient";
import type { Invoice } from "../../shared/types";
import { billingApi } from "./api";
export function useInvoices(setError: (message: string) => void) {
  const [detail, setDetail] = useState<Invoice | null>(null);
  const invoiceKey = useRef(uid()),
    paymentKey = useRef(uid());
  const openInvoice = async (id: string) => {
    try {
      const i = await billingApi.invoice(id);
      setDetail(i);
      paymentKey.current = uid();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return { detail, setDetail, invoiceKey, paymentKey, openInvoice };
}
