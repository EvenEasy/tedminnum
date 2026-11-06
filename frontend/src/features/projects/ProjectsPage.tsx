import { Empty } from "../../shared/ui";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function ProjectsPage(
  props: Pick<
    WorkspaceController,
    | "clients"
    | "isAdmin"
    | "projects"
    | "setEditor"
    | "setPage"
    | "setProjectFilter"
    | "tasks"
  >,
) {
  const {
    clients,
    isAdmin,
    projects,
    setEditor,
    setPage,
    setProjectFilter,
    tasks,
  } = props;

  return (
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
              / {tasks.filter((t) => t.project_id === p.id).length} visible
              tasks done
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
              <button onClick={() => setEditor({ kind: "project", item: p })}>
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
  );
}
