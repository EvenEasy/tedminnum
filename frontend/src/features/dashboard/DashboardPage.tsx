import { dateTime, duration } from "../../shared/format";
import type { Task } from "../../shared/types";
import { Empty, Money } from "../../shared/ui";
import { FinanceCards } from "../reports/FinanceCards";

import type { WorkspaceController } from "../../app/useWorkspaceController";
import { TaskCard } from "../tasks/TaskCard";
export function DashboardPage(
  props: Pick<
    WorkspaceController,
    | "workspace"
    | "workspace"
    | "busy"
    | "dash"
    | "isAdmin"
    | "moveTask"
    | "mutate"
    | "projectName"
    | "setEditor"
    | "setPage"
    | "start"
    | "taskName"
    | "tasks"
    | "timer"
  >,
) {
  const {
    busy,
    dash,
    isAdmin,
    moveTask,
    mutate,
    projectName,
    setEditor,
    setPage,
    start,
    taskName,
    tasks,
    timer,
  } = props;
  const money = (value: string) => (
    <Money value={value} currency={props.workspace.currency} />
  );
  const taskCard = (task: Task) => <TaskCard {...props} task={task} />;
  if (!dash) return null;
  return (
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
            <button className="text-button" onClick={() => setPage("Tasks")}>
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
            <button className="text-button" onClick={() => setPage("Time")}>
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
  );
}
