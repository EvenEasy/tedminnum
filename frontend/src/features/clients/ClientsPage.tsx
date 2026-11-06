import { Empty, Money } from "../../shared/ui";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function ClientsPage(
  props: Pick<
    WorkspaceController,
    "workspace" | "workspace" | "clients" | "isAdmin" | "projects" | "setEditor"
  >,
) {
  const { clients, isAdmin, projects, setEditor } = props;
  const money = (value: string) => (
    <Money value={value} currency={props.workspace.currency} />
  );

  return (
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
                <td>{projects.filter((p) => p.client_id === c.id).length}</td>
                {isAdmin && (
                  <>
                    <td>{money(c.rate || "0")}/h</td>
                    <td>
                      <button
                        onClick={() => setEditor({ kind: "client", item: c })}
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
  );
}
