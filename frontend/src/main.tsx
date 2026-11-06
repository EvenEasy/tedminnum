import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, all, setCSRF, uid } from "./api";
import type {
  User,
  Client,
  Project,
  Task,
  Entry,
  Invoice,
  Dashboard,
  Audit,
  Hook,
  Delivery,
  Workspace,
  Editor,
} from "./types";
import {
  statuses,
  label,
  duration,
  dateTime,
  today,
  formData,
  text,
  checked,
} from "./format";
import { ErrorMessage, Empty, Field, Status, Money, Modal } from "./components";
import { Login } from "./Login";
import { FinanceCards } from "./work-forms";
import { EditorDialog } from "./EditorDialog";
import "./style.css";

function App() {
  const [user, setUser] = useState<User | null>(null),
    [initial, setInitial] = useState(true),
    [page, setPage] = useState("Dashboard");
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
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [editor, setEditor] = useState<Editor | null>(null),
    [detail, setDetail] = useState<Invoice | null>(null);
  const [theme, setTheme] = useState(
      () => localStorage.getItem("theme") || "dark",
    ),
    [board, setBoard] = useState(true),
    [query, setQuery] = useState(""),
    [projectFilter, setProjectFilter] = useState(""),
    [period, setPeriod] = useState("all");
  const [timer, setTimer] = useState<Entry | null>(null),
    [serverOffset, setServerOffset] = useState(0),
    [tick, setTick] = useState(Date.now()),
    [timerTask, setTimerTask] = useState(""),
    [timerKind, setTimerKind] = useState("work"),
    [timerBillable, setTimerBillable] = useState(true),
    [longBreak, setLongBreak] = useState(false);
  const [audits, setAudits] = useState<Audit[]>([]),
    [hooks, setHooks] = useState<Hook[]>([]),
    [deliveries, setDeliveries] = useState<Delivery[]>([]),
    [hookSecret, setHookSecret] = useState("");
  const invoiceKey = useRef(uid()),
    paymentKey = useRef(uid()),
    timerKey = useRef(uid()),
    seenReminder = useRef("");
  const authEpoch = useRef(0);
  const switchUser = (next: User | null) => {
    authEpoch.current += 1;
    setClients([]);
    setProjects([]);
    setTasks([]);
    setEntries([]);
    setInvoices([]);
    setUsers([]);
    setDash(null);
    setTimer(null);
    setAudits([]);
    setHooks([]);
    setDeliveries([]);
    setHookSecret("");
    setDetail(null);
    setEditor(null);
    setError("");
    setNotice("");
    setPage("Dashboard");
    setWorkspace({ name: "Tedminnum", currency: "USD" });
    setUser(next);
  };
  const isAdmin = user?.role === "admin";
  const taskName = (id: string | null) =>
    tasks.find((t) => t.id === id)?.title || "Unassigned work";
  const projectName = (id: string) =>
    projects.find((p) => p.id === id)?.name || "Project";
  const money = (value: string) => (
    <Money value={value} currency={workspace.currency} />
  );
  const refreshTimer = useCallback(async () => {
    const epoch = authEpoch.current;
    const r = await api<{ entry: Entry | null; server_time: string }>("/timer");
    if (epoch !== authEpoch.current) return;
    setTimer(r.entry);
    setServerOffset(new Date(r.server_time).getTime() - Date.now());
  }, []);
  const load = useCallback(async () => {
    if (!user) return;
    const epoch = authEpoch.current;
    setLoading(true);
    try {
      const day = new Date();
      day.setHours(0, 0, 0, 0);
      const [c, p, t, e, d, s] = await Promise.all([
        all<Client>("/clients"),
        all<Project>("/projects"),
        all<Task>("/tasks"),
        all<Entry>("/time"),
        api<Dashboard>(
          "/dashboard?day_start=" + encodeURIComponent(day.toISOString()),
        ),
        api<{ workspace: Workspace }>("/settings"),
      ]);
      if (epoch !== authEpoch.current) return;
      setClients(c);
      setProjects(p);
      setTasks(t);
      setEntries(e);
      setDash(d);
      setWorkspace(s.workspace);
      await refreshTimer();
      if (user.role === "admin") {
        const [i, u] = await Promise.all([
          all<Invoice>("/invoices"),
          all<User>("/users"),
        ]);
        if (epoch !== authEpoch.current) return;
        setInvoices(i);
        setUsers(u);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [user, refreshTimer]);
  const mutate = async (action: () => Promise<unknown>, message = "Saved") => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      await load();
      setNotice(message);
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  useEffect(() => {
    api<{ user: User; csrf: string }>("/auth/me")
      .then((r) => {
        setUser(r.user);
        setCSRF(r.csrf);
      })
      .catch(() => {})
      .finally(() => setInitial(false));
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => {
      void refreshTimer().catch((e) => setError((e as Error).message));
    }, 10000);
    const focus = () => void load();
    window.addEventListener("focus", focus);
    return () => {
      clearInterval(id);
      window.removeEventListener("focus", focus);
    };
  }, [user, refreshTimer, load]);
  useEffect(() => {
    const id = setInterval(() => setTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const elapsed = timer
    ? Math.max(
        0,
        Math.floor(
          ((timer.paused_at
            ? new Date(timer.paused_at).getTime()
            : tick + serverOffset) -
            new Date(timer.started_at).getTime() -
            timer.paused_microseconds / 1000) /
            1000,
        ),
      )
    : 0;
  useEffect(() => {
    if (
      timer &&
      !timer.paused_at &&
      elapsed >= timer.target_seconds &&
      seenReminder.current !== timer.id
    ) {
      seenReminder.current = timer.id;
      setNotice(
        timer.kind === "work"
          ? "Focus session complete. Stop work and take a break when ready."
          : "Break complete. Ready for another focus session?",
      );
      if (
        user?.notifications &&
        "Notification" in window &&
        Notification.permission === "granted"
      )
        new Notification("Tedminnum", {
          body:
            timer.kind === "work"
              ? "Time for a break."
              : "Your break is complete.",
        });
    }
  }, [elapsed, timer, user]);
  useEffect(() => {
    if (!user || page !== "Settings" || user.role !== "admin") return;
    all<Audit>("/audit")
      .then(setAudits)
      .catch((e) => setError(e.message));
    api<{ items: Hook[]; deliveries: Delivery[] }>("/webhooks")
      .then((r) => {
        setHooks(r.items);
        setDeliveries(r.deliveries);
      })
      .catch((e) => setError(e.message));
  }, [user, page, notice]);
  const start = async (taskId?: string) => {
    if (
      await mutate(
        () =>
          api("/timer", "POST", {
            request_key: timerKey.current,
            task_id: taskId || timerTask || null,
            kind: taskId ? "work" : timerKind,
            billable: timerBillable,
            long_break: longBreak,
          }),
        "Timer started",
      )
    )
      timerKey.current = uid();
  };
  const command = async (c: string) => {
    if (timer)
      await mutate(
        () => api(`/timer/${timer.id}/${c}`, "POST"),
        c === "stop" ? "Session saved" : "Timer updated",
      );
  };
  const openInvoice = async (id: string) => {
    try {
      const i = await api<Invoice>(`/invoices/${id}`);
      setDetail(i);
      paymentKey.current = uid();
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const moveTask = async (t: Task, status: string, position = t.position) =>
    mutate(
      () =>
        api(`/tasks/${t.id}`, "PATCH", {
          version: t.version,
          status,
          position,
        }),
      "Task moved",
    );
  const filteredTasks = tasks.filter(
    (t) =>
      (!projectFilter || t.project_id === projectFilter) &&
      t.title.toLowerCase().includes(query.toLowerCase()),
  );
  const visibleEntries = entries.filter((e) => {
    if (period === "all") return true;
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    if (period === "week")
      start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
    if (period === "month") start.setDate(1);
    return new Date(e.started_at) >= start;
  });
  if (initial) return <main className="loading">Opening your workspace…</main>;
  if (!user) return <Login onLogin={switchUser} />;
  const nav = [
    "Dashboard",
    "Tasks",
    "Projects",
    "Time",
    "Clients",
    ...(isAdmin ? ["Invoices", "Reports"] : []),
    "Settings",
  ];
  const taskCard = (t: Task) => (
    <article className="task-card" key={t.id}>
      <div className="row">
        <span className={`priority ${t.priority}`}>{label(t.priority)}</span>
        <span className="small muted">{projectName(t.project_id)}</span>
      </div>
      <h3>{t.title}</h3>
      {t.description && <p className="task-description">{t.description}</p>}
      <div className="row small muted">
        <span>{t.due_date ? "Due " + t.due_date : "No due date"}</span>
        <span>
          {t.estimate_minutes ? `${t.estimate_minutes}m estimate` : ""}
        </span>
      </div>
      <div className="task-actions">
        <select
          aria-label={`Status for ${t.title}`}
          value={t.status}
          disabled={busy}
          onChange={(e) => void moveTask(t, e.target.value)}
        >
          {statuses.map((s) => (
            <option key={s} value={s}>
              {label(s)}
            </option>
          ))}
        </select>
        <button
          className="icon"
          title="Move earlier"
          aria-label={`Move ${t.title} earlier`}
          disabled={busy}
          onClick={() =>
            void mutate(
              () =>
                api(`/tasks/${t.id}/move`, "POST", {
                  version: t.version,
                  direction: "up",
                }),
              "Task moved",
            )
          }
        >
          ↑
        </button>
        <button
          className="icon"
          title="Move later"
          aria-label={`Move ${t.title} later`}
          disabled={busy}
          onClick={() =>
            void mutate(
              () =>
                api(`/tasks/${t.id}/move`, "POST", {
                  version: t.version,
                  direction: "down",
                }),
              "Task moved",
            )
          }
        >
          ↓
        </button>
        {isAdmin && (
          <button
            className="icon"
            aria-label={`Edit ${t.title}`}
            onClick={() => setEditor({ kind: "task", item: t })}
          >
            ✎
          </button>
        )}
        <button
          className="icon play"
          aria-label={`Track ${t.title}`}
          disabled={!!timer || busy}
          onClick={() => void start(t.id)}
        >
          ▶
        </button>
      </div>
    </article>
  );
  const entryTable = (items: Entry[]) => (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Work / break</th>
            <th>Started</th>
            <th>Duration</th>
            <th>Billing</th>
            <th>
              <span className="sr-only">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((e) => (
            <tr key={e.id}>
              <td>
                <strong>
                  {e.kind === "break" ? "Break" : taskName(e.task_id)}
                </strong>
                {e.note && <small>{e.note}</small>}
              </td>
              <td>{dateTime(e.started_at)}</td>
              <td className="mono">
                {duration(e.seconds)}
                {!e.ended_at && " · active"}
              </td>
              <td>
                {e.kind === "break"
                  ? "Non-billable"
                  : e.reserved
                    ? "Reserved / invoiced"
                    : e.billable
                      ? "Billable"
                      : "Non-billable"}
              </td>
              <td>
                {e.ended_at && !e.reserved && (
                  <button
                    className="text-button"
                    onClick={() => setEditor({ kind: "time", item: e })}
                  >
                    Adjust
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && (
        <Empty>No sessions yet. Start a timer to record your work.</Empty>
      )}
    </div>
  );
  return (
    <div className="app">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("Dashboard");
          }}
        >
          <span className="brandmark small-brand">t.</span>
          <span>
            tedminnum<small>{workspace.name}</small>
          </span>
        </a>
        <span className="nav-caption">WORKSPACE</span>
        <nav>
          {nav.map((n, i) => (
            <button
              key={n}
              aria-label={n}
              className={page === n ? "active" : ""}
              onClick={() => {
                setPage(n);
                setQuery("");
                setProjectFilter("");
                setError("");
              }}
            >
              <span className="nav-icon">
                {["◈", "▤", "▦", "◷", "◉", "▧", "▥", "⚙"][i]}
              </span>
              {n}
              {n === "Tasks" && (
                <span className="nav-count">
                  {tasks.filter((t) => t.status !== "done").length}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <button
            className="theme-button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? "☀ Light appearance" : "☾ Dark appearance"}
          </button>
          <div className="profile">
            <span className="avatar">
              {user.name.slice(0, 2).toUpperCase()}
            </span>
            <div>
              <strong>{user.name}</strong>
              <small>{label(user.role)}</small>
            </div>
            <button
              className="icon"
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST");
                  switchUser(null);
                  setCSRF("");
                  setDetail(null);
                  setEditor(null);
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              ↗
            </button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span>
            Workspace <span className="muted">/</span> <strong>{page}</strong>
          </span>
          <div className="row">
            <span className="connection">● Local workspace</span>
            <button
              className="icon"
              disabled={loading}
              aria-label="Refresh workspace"
              onClick={() => void load()}
            >
              ↻
            </button>
          </div>
        </header>
        <main className="content">
          <div className="page-title">
            <div>
              <p className="eyebrow">
                {page === "Dashboard"
                  ? new Date().toLocaleDateString(undefined, {
                      weekday: "long",
                      month: "long",
                      day: "numeric",
                    })
                  : "YOUR WORKSPACE"}
              </p>
              <h1>
                {page === "Dashboard"
                  ? `Hello, ${user.name.split(" ")[0]}.`
                  : page}
              </h1>
              <p className="muted">
                {
                  (
                    {
                      Dashboard: "Make room for your most meaningful work.",
                      Tasks: "A clear path from idea to done.",
                      Projects: "Keep every project and its people connected.",
                      Time: "An honest record of where your time goes.",
                      Clients: "The people you do great work with.",
                      Invoices:
                        "Turn completed work into clear, traceable invoices.",
                      Reports:
                        "Work estimates and invoice balances, kept distinct.",
                      Settings: "Make this workspace your own.",
                    } as Record<string, string>
                  )[page]
                }
              </p>
            </div>
            <div className="row">
              {loading && (
                <span role="status" className="small muted">
                  Syncing…
                </span>
              )}
              {isAdmin &&
                ["Tasks", "Projects", "Clients", "Invoices"].includes(page) && (
                  <button
                    className="primary"
                    onClick={() => {
                      invoiceKey.current = uid();
                      setEditor({
                        kind: (
                          {
                            Tasks: "task",
                            Projects: "project",
                            Clients: "client",
                            Invoices: "invoice",
                          } as Record<
                            string,
                            "task" | "project" | "client" | "invoice"
                          >
                        )[page],
                      });
                    }}
                  >
                    ＋ New{" "}
                    {page === "Invoices"
                      ? "invoice"
                      : page.slice(0, -1).toLowerCase()}
                  </button>
                )}
            </div>
          </div>
          <ErrorMessage error={error} />
          {notice && (
            <div className="alert success" role="status">
              <span>{notice}</span>
              <button
                className="icon"
                aria-label="Dismiss message"
                onClick={() => setNotice("")}
              >
                ×
              </button>
            </div>
          )}
          <section
            className={`timer-panel ${timer ? "running" : ""}`}
            aria-label="Focus timer"
          >
            <div>
              <span className="eyebrow">
                {timer
                  ? timer.kind === "break"
                    ? "TAKE A BREATH"
                    : "FOCUS IN PROGRESS"
                  : "TIME FOR YOUR NEXT GOOD IDEA"}
              </span>
              <h2>
                {timer
                  ? timer.kind === "break"
                    ? "On a break"
                    : taskName(timer.task_id)
                  : "One thing at a time."}
              </h2>
              {timer ? (
                <span className="small muted">
                  {timer.paused_at ? "Paused · " : ""}
                  {Math.round(timer.target_seconds / 60)} minute reminder ·{" "}
                  {timer.billable ? "Billable work" : "Non-billable"}
                </span>
              ) : (
                <div className="timer-options">
                  <select
                    aria-label="Timer task"
                    value={timerTask}
                    onChange={(e) => setTimerTask(e.target.value)}
                  >
                    <option value="">Work without a task</option>
                    {tasks
                      .filter((t) => t.status !== "done")
                      .map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.title}
                        </option>
                      ))}
                  </select>
                  <select
                    aria-label="Session type"
                    value={timerKind}
                    onChange={(e) => setTimerKind(e.target.value)}
                  >
                    <option value="work">Focus work</option>
                    <option value="break">Break</option>
                  </select>
                  {timerKind === "work" ? (
                    <label className="check small">
                      <input
                        type="checkbox"
                        checked={timerBillable}
                        onChange={(e) => setTimerBillable(e.target.checked)}
                      />
                      Billable
                    </label>
                  ) : (
                    <label className="check small">
                      <input
                        type="checkbox"
                        checked={longBreak}
                        onChange={(e) => setLongBreak(e.target.checked)}
                      />
                      Long break
                    </label>
                  )}
                </div>
              )}
            </div>
            <div className="timer-controls">
              <div className="timer-value mono" aria-live="off">
                {duration(elapsed)}
              </div>
              {timer ? (
                <>
                  <button
                    disabled={busy}
                    onClick={() =>
                      void command(timer.paused_at ? "resume" : "pause")
                    }
                  >
                    {timer.paused_at ? "Resume" : "Pause"}
                  </button>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => void command("stop")}
                  >
                    Stop & save
                  </button>
                </>
              ) : (
                <button
                  className="primary"
                  disabled={busy}
                  onClick={() => void start()}
                >
                  ▶ Start session
                </button>
              )}
            </div>
          </section>
          {page === "Dashboard" && dash && (
            <>
              <div className="stats">
                <article className="stat">
                  <span>Focus today</span>
                  <strong>{duration(dash.work_seconds)}</strong>
                  <small>Work sessions started today</small>
                </article>
                <article className="stat">
                  <span>Break time</span>
                  <strong>{duration(dash.break_seconds)}</strong>
                  <small>Always non-billable</small>
                </article>
                <article className="stat">
                  <span>Assigned to you</span>
                  <strong>
                    {dash.open_tasks}
                    <em>tasks</em>
                  </strong>
                  <small>Ready for your attention</small>
                </article>
                {isAdmin && dash.finance && (
                  <article className="stat accent">
                    <span>Invoice outstanding</span>
                    <strong>{money(dash.finance.outstanding)}</strong>
                    <small>Issued balance after payments</small>
                  </article>
                )}
              </div>
              <div className="dashboard-grid">
                <section className="panel">
                  <div className="panel-head">
                    <h2>Your next steps</h2>
                    <button
                      className="text-button"
                      onClick={() => setPage("Tasks")}
                    >
                      All tasks →
                    </button>
                  </div>
                  <div className="task-stack">
                    {dash.tasks.map(taskCard)}
                    {dash.tasks.length === 0 && (
                      <Empty>
                        You're all caught up. Assigned work will appear here.
                      </Empty>
                    )}
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-head">
                    <h2>Recent sessions</h2>
                    <button
                      className="text-button"
                      onClick={() => setPage("Time")}
                    >
                      View time →
                    </button>
                  </div>
                  {dash.recent.map((e) => (
                    <div className="activity" key={e.id}>
                      <span className={`activity-dot ${e.kind}`} />
                      <div>
                        <strong>
                          {e.kind === "break"
                            ? "A moment to recharge"
                            : taskName(e.task_id)}
                        </strong>
                        <small>{dateTime(e.started_at)}</small>
                      </div>
                      <span className="mono">{duration(e.seconds)}</span>
                    </div>
                  ))}
                  {dash.recent.length === 0 && (
                    <Empty>Your first session starts here.</Empty>
                  )}
                </section>
              </div>
              {dash.finance && <FinanceCards finance={dash.finance} />}
            </>
          )}
          {page === "Tasks" && (
            <>
              <div className="toolbar">
                <input
                  aria-label="Search tasks"
                  placeholder="Search tasks…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <select
                  aria-label="Filter by project"
                  value={projectFilter}
                  onChange={(e) => setProjectFilter(e.target.value)}
                >
                  <option value="">All projects</option>
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                <div className="segmented">
                  <button
                    className={board ? "selected" : ""}
                    onClick={() => setBoard(true)}
                  >
                    Board
                  </button>
                  <button
                    className={!board ? "selected" : ""}
                    onClick={() => setBoard(false)}
                  >
                    List
                  </button>
                </div>
              </div>
              {board ? (
                <div className="kanban">
                  {statuses.map((status) => (
                    <section className="column" key={status}>
                      <h2>
                        <span className={"status-dot " + status} />
                        {label(status)}
                        <span>
                          {
                            filteredTasks.filter((t) => t.status === status)
                              .length
                          }
                        </span>
                      </h2>
                      {filteredTasks
                        .filter((t) => t.status === status)
                        .map(taskCard)}
                      {!filteredTasks.some((t) => t.status === status) && (
                        <Empty>No tasks here yet.</Empty>
                      )}
                    </section>
                  ))}
                </div>
              ) : (
                <div className="task-list">{filteredTasks.map(taskCard)}</div>
              )}
            </>
          )}
          {page === "Projects" && (
            <div className="cards">
              {projects.map((p) => (
                <article className="panel project-card" key={p.id}>
                  <span className="project-symbol">
                    {p.name.slice(0, 1).toUpperCase()}
                  </span>
                  <h2>{p.name}</h2>
                  <p className="muted">
                    {clients.find((c) => c.id === p.client_id)?.name}
                  </p>
                  <div className="row">
                    <span>
                      {
                        tasks.filter(
                          (t) => t.project_id === p.id && t.status === "done",
                        ).length
                      }{" "}
                      / {tasks.filter((t) => t.project_id === p.id).length}{" "}
                      visible tasks done
                    </span>
                    {isAdmin && <span>{p.member_ids?.length} members</span>}
                  </div>
                  <div className="project-progress">
                    <span
                      style={{
                        width: `${tasks.filter((t) => t.project_id === p.id).length ? (tasks.filter((t) => t.project_id === p.id && t.status === "done").length / tasks.filter((t) => t.project_id === p.id).length) * 100 : 0}%`,
                      }}
                    />
                  </div>
                  <div className="row">
                    <button
                      className="text-button"
                      onClick={() => {
                        setPage("Tasks");
                        setProjectFilter(p.id);
                      }}
                    >
                      Open tasks →
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() => setEditor({ kind: "project", item: p })}
                      >
                        Edit project
                      </button>
                    )}
                  </div>
                </article>
              ))}
              {projects.length === 0 && (
                <Empty>
                  {isAdmin
                    ? "Create a client, then add your first project."
                    : "Your assigned projects will appear here."}
                </Empty>
              )}
            </div>
          )}
          {page === "Clients" && (
            <section className="panel">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Client</th>
                      <th>Projects</th>
                      {isAdmin && (
                        <>
                          <th>Default hourly rate</th>
                          <th>Actions</th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {clients.map((c) => (
                      <tr key={c.id}>
                        <td>
                          <strong>{c.name}</strong>
                        </td>
                        <td>
                          {projects.filter((p) => p.client_id === c.id).length}
                        </td>
                        {isAdmin && (
                          <>
                            <td>{money(c.rate || "0")}/h</td>
                            <td>
                              <button
                                onClick={() =>
                                  setEditor({ kind: "client", item: c })
                                }
                              >
                                Edit client
                              </button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {clients.length === 0 && <Empty>No clients yet.</Empty>}
            </section>
          )}
          {page === "Time" && (
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>Time journal</h2>
                  <p className="muted small">
                    Grouped by session start ·{" "}
                    {duration(
                      visibleEntries.reduce((a, e) => a + e.seconds, 0),
                    )}{" "}
                    total
                  </p>
                </div>
                <select
                  aria-label="Time period"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                >
                  <option value="all">All time</option>
                  <option value="day">Today</option>
                  <option value="week">This week</option>
                  <option value="month">This month</option>
                </select>
              </div>
              {entryTable(visibleEntries)}
            </section>
          )}
          {page === "Invoices" && (
            <section className="panel">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Invoice</th>
                      <th>Client</th>
                      <th>Created</th>
                      <th>Status</th>
                      <th>Total</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((i) => (
                      <tr key={i.id}>
                        <td>
                          <strong>{i.number}</strong>
                        </td>
                        <td>{i.client_name}</td>
                        <td>{new Date(i.created_at).toLocaleDateString()}</td>
                        <td>
                          <Status value={i.status} />
                        </td>
                        <td>
                          <Money value={i.total} currency={i.currency} />
                        </td>
                        <td>
                          <button onClick={() => void openInvoice(i.id)}>
                            Open invoice
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {invoices.length === 0 && (
                <Empty>
                  No invoices yet. Select completed billable work to create a
                  draft.
                </Empty>
              )}
            </section>
          )}
          {page === "Reports" && isAdmin && dash?.finance && (
            <>
              <FinanceCards finance={dash.finance} />
              <section className="panel prose">
                <h2>Understand the numbers</h2>
                <p>
                  Worked value estimates completed hourly work at current rates,
                  plus finished fixed-price tasks once each. Time logged on
                  fixed-price tasks adds no hourly charges.
                </p>
                <p>
                  Uninvoiced value excludes work reserved by drafts or included
                  in issued invoices. Draft reserved value uses the draft's
                  saved prices. Issued outstanding and payments received use
                  immutable invoice amounts.
                </p>
                <p>
                  These values describe different stages of the same work. Do
                  not add them together. No tax, currency conversion, or
                  accounting ledger is included.
                </p>
                <p>
                  Rate precedence: task override → project override → client
                  default. Money rounds half up per line to two decimal places.
                  A time line calculates from exact integer seconds; displayed
                  hours are rounded.
                </p>
              </section>
            </>
          )}
          {page === "Settings" && (
            <div className="settings-grid">
              <section className="panel">
                <div className="panel-head">
                  <h2>Focus & reminders</h2>
                  <button
                    type="button"
                    onClick={() =>
                      setTheme(theme === "dark" ? "light" : "dark")
                    }
                  >
                    Switch to {theme === "dark" ? "light" : "dark"} appearance
                  </button>
                </div>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = formData(e);
                    const prefs = {
                      work_minutes: Number(text(f, "work_minutes")),
                      short_break: Number(text(f, "short_break")),
                      long_break: Number(text(f, "long_break")),
                      notifications: checked(f, "notifications"),
                    };
                    if (prefs.notifications && "Notification" in window) {
                      const permission = await Notification.requestPermission();
                      if (permission !== "granted") {
                        setError(
                          "Browser notifications were not granted. In-app reminders remain active.",
                        );
                        prefs.notifications = false;
                      }
                    }
                    const r = await mutate(
                      () => api<User>("/settings/preferences", "PATCH", prefs),
                      "Focus preferences saved",
                    );
                    if (r) setUser({ ...user, ...prefs });
                  }}
                >
                  <div className="form-grid">
                    <Field title="Focus minutes">
                      <input
                        name="work_minutes"
                        type="number"
                        min="1"
                        max="180"
                        defaultValue={user.work_minutes}
                        required
                      />
                    </Field>
                    <Field title="Short break minutes">
                      <input
                        name="short_break"
                        type="number"
                        min="1"
                        max="60"
                        defaultValue={user.short_break}
                        required
                      />
                    </Field>
                    <Field title="Long break minutes">
                      <input
                        name="long_break"
                        type="number"
                        min="1"
                        max="120"
                        defaultValue={user.long_break}
                        required
                      />
                    </Field>
                  </div>
                  <label className="check">
                    <input
                      name="notifications"
                      type="checkbox"
                      defaultChecked={user.notifications}
                    />
                    Browser notifications
                  </label>
                  <p className="small muted">
                    Reminders work while this app is open. Timers continue until
                    you stop them. Choose a short or long break when starting a
                    break session.
                  </p>
                  <button className="primary" disabled={busy}>
                    Save preferences
                  </button>
                </form>
              </section>
              <section className="panel">
                <h2>Change your password</h2>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const f = formData(e);
                    if (
                      await mutate(
                        () =>
                          api("/auth/password", "POST", {
                            current_password: text(f, "current"),
                            new_password: text(f, "new"),
                          }),
                        "Password changed. Please sign in again.",
                      )
                    )
                      switchUser(null);
                  }}
                >
                  <Field title="Current password">
                    <input
                      name="current"
                      type="password"
                      autoComplete="current-password"
                      required
                    />
                  </Field>
                  <Field title="New password">
                    <input
                      name="new"
                      type="password"
                      minLength={12}
                      maxLength={128}
                      autoComplete="new-password"
                      required
                    />
                  </Field>
                  <button disabled={busy}>Change password & sign out</button>
                </form>
              </section>
              {isAdmin && (
                <>
                  <section className="panel">
                    <h2>Workspace</h2>
                    <form
                      key={workspace.currency + workspace.name}
                      onSubmit={(e) => {
                        e.preventDefault();
                        const f = formData(e);
                        void mutate(
                          () =>
                            api("/settings/workspace", "PATCH", {
                              name: text(f, "name"),
                              currency: text(f, "currency"),
                            }),
                          "Workspace saved",
                        );
                      }}
                    >
                      <Field title="Name">
                        <input
                          name="name"
                          defaultValue={workspace.name}
                          required
                          maxLength={200}
                        />
                      </Field>
                      <Field title="Currency">
                        <select
                          name="currency"
                          defaultValue={workspace.currency}
                        >
                          {[
                            "USD",
                            "EUR",
                            "GBP",
                            "UAH",
                            "CAD",
                            "PLN",
                            "CHF",
                            "AUD",
                          ].map((c) => (
                            <option key={c}>{c}</option>
                          ))}
                        </select>
                      </Field>
                      <p className="small muted">
                        Currency is locked once clients or invoices exist.
                      </p>
                      <button disabled={busy}>Save workspace</button>
                    </form>
                  </section>
                  <section className="panel">
                    <div className="panel-head">
                      <h2>People & access</h2>
                      <button onClick={() => setEditor({ kind: "user" })}>
                        ＋ Add person
                      </button>
                    </div>
                    {users.map((u) => (
                      <div className="user-row" key={u.id}>
                        <div>
                          <strong>{u.name}</strong>
                          <small>{u.email}</small>
                        </div>
                        <select
                          aria-label={`Role for ${u.name}`}
                          value={u.role}
                          disabled={busy}
                          onChange={(e) => {
                            const role = e.target.value;
                            if (
                              confirm(
                                `Change ${u.name}'s role to ${role}? Existing sessions will be revoked.`,
                              )
                            )
                              void mutate(
                                () =>
                                  api(`/users/${u.id}`, "PATCH", {
                                    role,
                                    active: u.active,
                                  }),
                                "User updated",
                              );
                          }}
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                        <button
                          disabled={busy}
                          onClick={() => {
                            if (
                              confirm(
                                `${u.active ? "Disable" : "Enable"} ${u.name}? Existing sessions will be revoked.`,
                              )
                            )
                              void mutate(
                                () =>
                                  api(`/users/${u.id}`, "PATCH", {
                                    role: u.role,
                                    active: !u.active,
                                  }),
                                "User updated",
                              );
                          }}
                        >
                          {u.active ? "Disable" : "Enable"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => {
                            setEditor({ kind: "reset", item: u });
                          }}
                        >
                          Reset password
                        </button>
                      </div>
                    ))}
                  </section>
                  <section className="panel full">
                    <h2>Outgoing webhooks</h2>
                    <p className="small muted">
                      HTTPS hosts must be allowed in WEBHOOK_HOSTS. Secrets are
                      shown once. Signed events retry up to six times.
                    </p>
                    <form
                      className="inline-form"
                      onSubmit={async (e) => {
                        e.preventDefault();
                        const f = formData(e);
                        await mutate(async () => {
                          const h = await api<Hook & { secret: string }>(
                            "/webhooks",
                            "POST",
                            { url: text(f, "url") },
                          );
                          setHookSecret(h.secret);
                        }, "Webhook created");
                      }}
                    >
                      <input
                        name="url"
                        aria-label="Webhook HTTPS URL"
                        type="url"
                        placeholder="https://allowed-host.example/events"
                        required
                      />
                      <button disabled={busy}>Add endpoint</button>
                    </form>
                    {hookSecret && (
                      <div className="alert success">
                        <strong>Copy this secret now:</strong>
                        <code className="secret">{hookSecret}</code>
                        <button onClick={() => setHookSecret("")}>Hide</button>
                      </div>
                    )}
                    {hooks.map((h) => (
                      <div className="user-row" key={h.id}>
                        <span className="break-text">{h.url}</span>
                        <Status value={h.enabled ? "enabled" : "disabled"} />
                        <button
                          disabled={busy}
                          onClick={() =>
                            void mutate(
                              () =>
                                api(`/webhooks/${h.id}`, "PATCH", {
                                  enabled: !h.enabled,
                                }),
                              "Webhook updated",
                            )
                          }
                        >
                          {h.enabled ? "Disable" : "Enable"}
                        </button>
                        <button
                          disabled={busy}
                          onClick={() => {
                            if (
                              confirm(
                                "Rotate this secret? Update your receiver before new deliveries.",
                              )
                            )
                              void mutate(async () => {
                                const r = await api<{ secret: string }>(
                                  `/webhooks/${h.id}`,
                                  "PATCH",
                                  { enabled: h.enabled, rotate_secret: true },
                                );
                                setHookSecret(r.secret);
                              }, "Secret rotated");
                          }}
                        >
                          Rotate secret
                        </button>
                      </div>
                    ))}
                    {deliveries.slice(0, 20).map((d) => (
                      <div className="activity" key={d.id}>
                        <div>
                          <strong>{d.event}</strong>
                          <small>{d.id}</small>
                        </div>
                        <span>
                          {d.delivered_at
                            ? "Delivered"
                            : d.attempts >= 6
                              ? "Exhausted"
                              : "Pending"}{" "}
                          · {d.attempts} attempts · {d.status_code ?? "—"}
                        </span>
                      </div>
                    ))}
                  </section>
                  <section className="panel full">
                    <h2>Audit history</h2>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>When</th>
                            <th>Action</th>
                            <th>Object</th>
                            <th>Detail</th>
                          </tr>
                        </thead>
                        <tbody>
                          {audits.map((a) => (
                            <tr key={a.id}>
                              <td>{dateTime(a.created_at)}</td>
                              <td>{a.action}</td>
                              <td className="mono small">{a.object_id}</td>
                              <td>{a.detail}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}
            </div>
          )}
        </main>
        <footer className="footer">
          A calmer place to get things done.<span>Tedminnum · Self-hosted</span>
        </footer>
      </div>
      {editor && (
        <EditorDialog
          editor={editor}
          error={error}
          busy={busy}
          mutate={mutate}
          onClose={() => setEditor(null)}
          clients={clients}
          projects={projects}
          tasks={tasks}
          entries={entries}
          users={users}
          workspace={workspace}
          invoiceKey={invoiceKey}
        />
      )}
      {detail && (
        <Modal title={detail.number} onClose={() => setDetail(null)}>
          <ErrorMessage error={error} />
          <div className="row">
            <div>
              <h3>{detail.client_name}</h3>
              <p className="muted">
                {new Date(detail.created_at).toLocaleDateString()}
              </p>
            </div>
            <Status value={detail.status} />
          </div>
          <div className="invoice-lines">
            {detail.lines?.map((line) => (
              <div key={line.id}>
                <div>
                  <strong>{line.description}</strong>
                  <small>
                    {Number(line.quantity).toFixed(6)} × {line.rate}{" "}
                    {detail.currency}
                  </small>
                  {detail.status === "draft" && (
                    <button
                      className="text-button"
                      onClick={async () => {
                        const description = prompt(
                          "Line description",
                          line.description,
                        );
                        if (
                          description &&
                          (await mutate(
                            () =>
                              api(
                                `/invoices/${detail.id}/lines/${line.id}`,
                                "PATCH",
                                { description },
                              ),
                            "Description saved",
                          ))
                        )
                          await openInvoice(detail.id);
                      }}
                    >
                      Edit description
                    </button>
                  )}
                </div>
                <strong>
                  <Money value={line.amount} currency={detail.currency} />
                </strong>
              </div>
            ))}
          </div>
          <div className="invoice-total">
            <span>Total</span>
            <strong>
              <Money value={detail.total} currency={detail.currency} />
            </strong>
          </div>
          <div className="invoice-total">
            <span>Received</span>
            <span>
              <Money
                value={String(
                  detail.payments?.reduce(
                    (sum, p) => sum + Math.round(Number(p.amount) * 100),
                    0,
                  )! / 100 || 0,
                )}
                currency={detail.currency}
              />
            </span>
          </div>
          <div className="form-actions">
            <a
              className="button"
              href={`/api/v1/invoices/${detail.id}/pdf`}
              download
            >
              Download PDF
            </a>
            {detail.status === "draft" && (
              <button
                className="primary"
                disabled={busy}
                onClick={async () => {
                  if (
                    confirm(
                      `Issue ${detail.number} for ${detail.total} ${detail.currency}? Amounts will be immutable.`,
                    ) &&
                    (await mutate(
                      () => api(`/invoices/${detail.id}/issue`, "POST"),
                      "Invoice issued",
                    ))
                  )
                    await openInvoice(detail.id);
                }}
              >
                Issue invoice
              </button>
            )}
            {!["void", "paid", "partially_paid"].includes(detail.status) && (
              <button
                className="danger"
                disabled={busy}
                onClick={async () => {
                  if (
                    confirm(
                      "Void this invoice and release its work for rebilling?",
                    ) &&
                    (await mutate(
                      () => api(`/invoices/${detail.id}/void`, "POST"),
                      "Invoice voided",
                    ))
                  )
                    await openInvoice(detail.id);
                }}
              >
                Void
              </button>
            )}
          </div>
          {["issued", "partially_paid"].includes(detail.status) && (
            <form
              className="payment-form"
              onSubmit={async (e) => {
                e.preventDefault();
                const f = formData(e);
                if (
                  await mutate(
                    () =>
                      api(`/payments?invoice_id=${detail.id}`, "POST", {
                        request_key: paymentKey.current,
                        amount: text(f, "amount"),
                        currency: detail.currency,
                        paid_on: text(f, "paid_on"),
                        reference: text(f, "reference"),
                      }),
                    "Payment recorded",
                  )
                )
                  await openInvoice(detail.id);
              }}
            >
              <h3>Record a payment</h3>
              <div className="form-grid">
                <Field title={`Amount (${detail.currency})`}>
                  <input
                    name="amount"
                    type="number"
                    step="0.01"
                    min="0.01"
                    required
                    defaultValue={(
                      (Math.round(Number(detail.total) * 100) -
                        (detail.payments || []).reduce(
                          (sum, p) => sum + Math.round(Number(p.amount) * 100),
                          0,
                        )) /
                      100
                    ).toFixed(2)}
                  />
                </Field>
                <Field title="Payment date">
                  <input
                    name="paid_on"
                    type="date"
                    defaultValue={today()}
                    required
                  />
                </Field>
              </div>
              <Field title="Reference (optional)">
                <input name="reference" maxLength={200} />
              </Field>
              <button className="primary" disabled={busy}>
                Record payment
              </button>
            </form>
          )}
          {detail.payments?.map((p) => (
            <div className="activity" key={p.id}>
              <div>
                <strong>Payment · {p.paid_on}</strong>
                <small>{p.reference || "No reference"}</small>
              </div>
              <span>
                <Money value={p.amount} currency={p.currency} />
              </span>
            </div>
          ))}
        </Modal>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
