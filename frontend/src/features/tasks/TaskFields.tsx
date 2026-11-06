import { useState } from "react";
import { label, statuses } from "../../shared/format";
import type { Project, Task, User } from "../../shared/types";
import { Field } from "../../shared/ui";
export function TaskFields({
  item,
  projects,
  users,
  currency,
}: {
  item?: Task;
  projects: Project[];
  users: User[];
  currency: string;
}) {
  const [projectId, setProjectId] = useState(item?.project_id || ""),
    [billing, setBilling] = useState(item?.billing || "hourly");
  const project = projects.find((p) => p.id === projectId);
  return (
    <>
      <Field title="Title">
        <input
          name="title"
          required
          maxLength={200}
          defaultValue={item?.title}
        />
      </Field>
      {!item && (
        <Field title="Project">
          <select
            name="project_id"
            required
            value={projectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            <option value="">Select a project</option>
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </Field>
      )}
      <Field title="Description">
        <textarea
          name="description"
          maxLength={10000}
          defaultValue={item?.description}
        />
      </Field>
      <div className="form-grid">
        <Field title="Status">
          <select name="status" defaultValue={item?.status || "backlog"}>
            {statuses.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </Field>
        <Field title="Priority">
          <select name="priority" defaultValue={item?.priority || "normal"}>
            {["low", "normal", "high", "urgent"].map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </Field>
        <Field title="Due date">
          <input
            name="due_date"
            type="date"
            defaultValue={item?.due_date || ""}
          />
        </Field>
        <Field title="Estimate (minutes)">
          <input
            name="estimate_minutes"
            type="number"
            min="0"
            max="1000000"
            defaultValue={item?.estimate_minutes ?? ""}
          />
        </Field>
        <Field title="Sort position">
          <input
            name="position"
            type="number"
            min="0"
            max="1000000"
            defaultValue={item?.position || 0}
          />
        </Field>
        <Field title="Billing mode">
          <select
            name="billing"
            value={billing}
            onChange={(e) => setBilling(e.target.value)}
          >
            <option value="hourly">Hourly</option>
            <option value="fixed">Fixed price</option>
            <option value="nonbillable">Non-billable</option>
          </select>
        </Field>
      </div>
      <Field
        title={
          billing === "fixed"
            ? `Fixed price (${currency})`
            : "Hourly override (blank inherits project / client)"
        }
      >
        <input
          name={billing === "fixed" ? "fixed_price" : "rate"}
          key={billing}
          type="number"
          min="0"
          max="9999999999"
          step="0.01"
          required={billing === "fixed"}
          defaultValue={
            (billing === "fixed" ? item?.fixed_price : item?.rate) || ""
          }
        />
      </Field>
      <fieldset>
        <legend>Task assignees</legend>
        {users
          .filter((u) => u.active && project?.member_ids?.includes(u.id))
          .map((u) => (
            <label className="check" key={u.id}>
              <input
                type="checkbox"
                name="assignees"
                value={u.id}
                defaultChecked={item?.assignee_ids.includes(u.id)}
              />
              {u.name}
            </label>
          ))}
        {!project?.member_ids?.length && (
          <p className="small muted">
            Add members to the project to assign this task.
          </p>
        )}
      </fieldset>
    </>
  );
}
