import { useEffect, useRef, useState } from "react";
import { useInvoices } from "../features/billing/useInvoices";
import { useSettingsData } from "../features/settings/useSettingsData";
import { useTasks } from "../features/tasks/useTasks";
import { useTimer } from "../features/tracking/useTimer";
import { useTimerActions } from "../features/tracking/useTimerActions";
import { credentialGeneration } from "../shared/apiClient";
import { useTheme } from "../shared/ThemeProvider";
import type { Editor, User } from "../shared/types";
import { useWorkspaceData } from "./useWorkspaceData";

import { useAuth } from "../features/auth/AuthProvider";
export function useWorkspaceController() {
  const auth = useAuth();
  const user = auth.user!;
  const setUser = auth.updateUser;
  const switchUser = (_next: User | null = null) => auth.clear();
  const [page, setPage] = useState("Dashboard");
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [editor, setEditor] = useState<Editor | null>(null);
  const { theme, setTheme } = useTheme();
  const [period, setPeriod] = useState("all");
  const isAdmin = user?.role === "admin";
  const timerState = useTimer(user, setNotice, setError);
  const {
    timer,
    timerTask,
    setTimerTask,
    timerKind,
    setTimerKind,
    timerBillable,
    setTimerBillable,
    longBreak,
    setLongBreak,
    elapsed,
    refreshTimer,
  } = timerState;
  const {
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
  } = useWorkspaceData(user, refreshTimer, setError);
  const { detail, setDetail, invoiceKey, paymentKey, openInvoice } =
    useInvoices(setError);
  const { audits, hooks, deliveries, hookSecret, setHookSecret } =
    useSettingsData(user, page, notice, setError);
  const operationScope = useRef(0);
  useEffect(
    () => () => {
      operationScope.current += 1;
    },
    [],
  );
  const mutate = async (action: () => Promise<unknown>, message = "Saved") => {
    const scope = operationScope.current,
      credentials = credentialGeneration();
    const current = () =>
      scope === operationScope.current &&
      credentials === credentialGeneration();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      if (!current()) return false;
      await load();
      if (!current()) return false;
      setNotice(message);
      return true;
    } catch (e) {
      if (current()) setError((e as Error).message);
      return false;
    } finally {
      if (current()) setBusy(false);
    }
  };
  const { start, command } = useTimerActions(timerState, mutate);
  const {
    board,
    setBoard,
    query,
    setQuery,
    projectFilter,
    setProjectFilter,
    filteredTasks,
    moveTask,
  } = useTasks(tasks, mutate);
  const taskName = (id: string | null) =>
    tasks.find((t) => t.id === id)?.title || "Unassigned work";
  const projectName = (id: string) =>
    projects.find((p) => p.id === id)?.name || "Project";
  const visibleEntries = entries.filter((e) => {
    if (period === "all") return true;
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    if (period === "week")
      start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    if (period === "month") start.setDate(1);
    return new Date(e.started_at) >= start;
  });

  const nav = [
    "Dashboard",
    "Tasks",
    "Projects",
    "Time",
    "Clients",
    ...(isAdmin ? ["Invoices", "Reports"] : []),
    "Settings",
  ];
  return {
    projectName,
    busy,
    moveTask,
    mutate,
    isAdmin,
    setEditor,
    timer,
    start,
    taskName,
    timerTask,
    setTimerTask,
    tasks,
    timerKind,
    setTimerKind,
    timerBillable,
    setTimerBillable,
    longBreak,
    setLongBreak,
    elapsed,
    command,
    dash,
    setPage,
    query,
    setQuery,
    projectFilter,
    setProjectFilter,
    projects,
    board,
    setBoard,
    filteredTasks,
    clients,
    visibleEntries,
    period,
    setPeriod,
    invoices,
    openInvoice,
    setTheme,
    theme,
    setError,
    setUser,
    user,
    switchUser,
    workspace,
    users,
    setHookSecret,
    hookSecret,
    hooks,
    deliveries,
    audits,
    detail,
    setDetail,
    error,
    paymentKey,
    nav,
    page,
    loading,
    load,
    invoiceKey,
    notice,
    setNotice,
    editor,
    entries,
  };
}
export type WorkspaceController = ReturnType<typeof useWorkspaceController>;
