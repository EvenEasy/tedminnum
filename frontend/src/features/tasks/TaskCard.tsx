import { label, statuses } from "../../shared/format";
import type { Task } from "../../shared/types";
import { taskApi } from "./api";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function TaskCard({
  busy,
  isAdmin,
  moveTask,
  mutate,
  projectName,
  setEditor,
  start,
  timer,
  task,
}: Pick<
  WorkspaceController,
  | "busy"
  | "isAdmin"
  | "moveTask"
  | "mutate"
  | "projectName"
  | "setEditor"
  | "start"
  | "timer"
> & { task: Task }) {
  const t = task;
  return (
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
                taskApi.move(t.id, {
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
                taskApi.move(t.id, {
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
}
