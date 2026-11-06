import { uid } from "../shared/apiClient";
import { label } from "../shared/format";
import { ErrorMessage } from "../shared/ui";
import { EditorDialog } from "./EditorDialog";

import { useAuth } from "../features/auth/AuthProvider";
import { InvoiceDetail } from "../features/billing/InvoiceDetail";
import { InvoicesPage } from "../features/billing/InvoicesPage";
import { ClientsPage } from "../features/clients/ClientsPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { ReportsPage } from "../features/reports/ReportsPage";
import { SettingsPage } from "../features/settings/SettingsPage";
import { TasksPage } from "../features/tasks/TasksPage";
import { TimePage } from "../features/tracking/TimePage";
import { TimerPanel } from "../features/tracking/TimerPanel";
import { useWorkspaceController } from "./useWorkspaceController";
export function WorkspaceApp() {
  const auth = useAuth();
  const user = auth.user!;
  const controller = useWorkspaceController();
  const {
    setPage,
    workspace,
    nav,
    page,
    setQuery,
    setProjectFilter,
    setError,
    tasks,
    setTheme,
    theme,
    switchUser,
    setDetail,
    setEditor,
    loading,
    load,
    isAdmin,
    invoiceKey,
    error,
    notice,
    setNotice,
    timer,
    taskName,
    timerTask,
    setTimerTask,
    timerKind,
    setTimerKind,
    timerBillable,
    setTimerBillable,
    longBreak,
    setLongBreak,
    elapsed,
    busy,
    command,
    start,
    dash,
    query,
    projectFilter,
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
    mutate,
    setUser,
    users,
    setHookSecret,
    hookSecret,
    hooks,
    deliveries,
    audits,
    detail,
    editor,
    entries,
    paymentKey,
    projectName,
    moveTask,
  } = controller;
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
                  await auth.logout();
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
          <TimerPanel {...controller} />
          {page === "Dashboard" && <DashboardPage {...controller} />}
          {page === "Tasks" && <TasksPage {...controller} />}
          {page === "Projects" && <ProjectsPage {...controller} />}
          {page === "Clients" && <ClientsPage {...controller} />}
          {page === "Time" && <TimePage {...controller} />}
          {page === "Invoices" && <InvoicesPage {...controller} />}
          {page === "Reports" && <ReportsPage {...controller} />}
          {page === "Settings" && <SettingsPage {...controller} />}
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
      <InvoiceDetail {...controller} />
    </div>
  );
}
