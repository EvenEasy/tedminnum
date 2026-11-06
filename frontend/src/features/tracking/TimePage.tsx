import { duration } from "../../shared/format";
import type { Entry } from "../../shared/types";

import type { WorkspaceController } from "../../app/useWorkspaceController";
import { EntryTable } from "./EntryTable";
export function TimePage(
  props: Pick<
    WorkspaceController,
    "period" | "setEditor" | "setPeriod" | "taskName" | "visibleEntries"
  >,
) {
  const { period, setEditor, setPeriod, taskName, visibleEntries } = props;
  const entryTable = (items: Entry[]) => (
    <EntryTable {...props} items={items} />
  );

  return (
    <section className="panel">
      <div className="panel-head">
        <div>
          <h2>Time journal</h2>
          <p className="muted small">
            Grouped by session start ·{" "}
            {duration(visibleEntries.reduce((a, e) => a + e.seconds, 0))} total
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
  );
}
