import { useCallback, useEffect, useRef, useState } from "react";
import { billingApi } from "../features/billing/api";
import { clientApi } from "../features/clients/api";
import { dashboardApi } from "../features/dashboard/api";
import { projectApi } from "../features/projects/api";
import { settingsApi } from "../features/settings/api";
import { taskApi } from "../features/tasks/api";
import { trackingApi } from "../features/tracking/api";
import type {
  Client,
  Dashboard,
  Entry,
  Invoice,
  Project,
  Task,
  User,
  Workspace,
} from "../shared/types";

export function useWorkspaceData(
  user: User,
  refreshTimer: () => Promise<void>,
  setError: (message: string) => void,
) {
  const scope = useRef(0),
    sequence = useRef(0);
  const [loading, setLoading] = useState(false);
  const [clients, setClients] = useState<Client[]>([]),
    [projects, setProjects] = useState<Project[]>([]),
    [tasks, setTasks] = useState<Task[]>([]),
    [entries, setEntries] = useState<Entry[]>([]),
    [invoices, setInvoices] = useState<Invoice[]>([]),
    [users, setUsers] = useState<User[]>([]),
    [dash, setDash] = useState<Dashboard | null>(null),
    [workspace, setWorkspace] = useState<Workspace>({
      name: "Tedminnum",
      currency: "USD",
    });
  const load = useCallback(async () => {
    if (!user) return;
    const epoch = scope.current,
      request = ++sequence.current;
    const current = () =>
      epoch === scope.current && request === sequence.current;
    setLoading(true);
    try {
      const day = new Date();
      day.setHours(0, 0, 0, 0);
      const [c, p, t, e, d, s] = await Promise.all([
        clientApi.list(),
        projectApi.list(),
        taskApi.list(),
        trackingApi.entries(),
        dashboardApi.summary(day.toISOString()),
        settingsApi.get(),
      ]);
      if (!current()) return;
      setClients(c);
      setProjects(p);
      setTasks(t);
      setEntries(e);
      setDash(d);
      setWorkspace(s.workspace);
      await refreshTimer();
      if (user.role === "admin") {
        const [i, u] = await Promise.all([
          billingApi.list(),
          settingsApi.users(),
        ]);
        if (!current()) return;
        setInvoices(i);
        setUsers(u);
      }
    } catch (e) {
      if (current()) setError((e as Error).message);
    } finally {
      if (current()) setLoading(false);
    }
  }, [user, refreshTimer]);
  useEffect(() => {
    void load();
    const focus = () => void load();
    window.addEventListener("focus", focus);
    return () => {
      scope.current += 1;
      window.removeEventListener("focus", focus);
    };
  }, [load]);
  return {
    clients,
    projects,
    tasks,
    entries,
    invoices,
    users,
    dash,
    workspace,
    loading,
    load,
  };
}
