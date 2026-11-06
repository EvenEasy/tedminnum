import { label, statuses } from "../../shared/format";
import type { Task } from "../../shared/types";
import { Empty } from "../../shared/ui";

import type { WorkspaceController } from "../../app/useWorkspaceController";
import { TaskCard } from "./TaskCard";
export function TasksPage(
  props: Pick<
    WorkspaceController,
    | "board"
    | "busy"
    | "filteredTasks"
    | "isAdmin"
    | "moveTask"
    | "mutate"
    | "projectFilter"
    | "projectName"
    | "projects"
    | "query"
    | "setBoard"
    | "setEditor"
    | "setProjectFilter"
    | "setQuery"
    | "start"
    | "timer"
  >,
) {
  const {
    board,
    busy,
    filteredTasks,
    isAdmin,
    moveTask,
    mutate,
    projectFilter,
    projectName,
    projects,
    query,
    setBoard,
    setEditor,
    setProjectFilter,
    setQuery,
    start,
    timer,
  } = props;
  const taskCard = (task: Task) => <TaskCard {...props} task={task} />;

  return (
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
                  {filteredTasks.filter((t) => t.status === status).length}
                </span>
              </h2>
              {filteredTasks.filter((t) => t.status === status).map(taskCard)}
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
  );
}
