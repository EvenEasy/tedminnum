import { useEffect, useState } from "react";
import type { Audit, Delivery, Hook, User } from "../../shared/types";
import { settingsApi } from "./api";
export function useSettingsData(
  user: User,
  page: string,
  notice: string,
  setError: (message: string) => void,
) {
  const [audits, setAudits] = useState<Audit[]>([]),
    [hooks, setHooks] = useState<Hook[]>([]),
    [deliveries, setDeliveries] = useState<Delivery[]>([]),
    [hookSecret, setHookSecret] = useState("");
  useEffect(() => {
    if (!user || page !== "Settings" || user.role !== "admin") return;
    let active = true;
    settingsApi
      .audit()
      .then((value) => {
        if (active) setAudits(value);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    settingsApi
      .hooks()
      .then((r) => {
        if (!active) return;
        setHooks(r.items);
        setDeliveries(r.deliveries);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [user, page, notice, setError]);
  return { audits, hooks, deliveries, hookSecret, setHookSecret };
}
