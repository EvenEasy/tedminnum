import { dateTime, duration } from "../../shared/format";
import type { Entry } from "../../shared/types";
import { Empty } from "../../shared/ui";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function EntryTable({
  setEditor,
  taskName,
  items,
}: Pick<WorkspaceController, "setEditor" | "taskName"> & { items: Entry[] }) {
  return (
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
}
