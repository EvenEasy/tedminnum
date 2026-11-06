import { useState, useEffect } from "react";
import { api, all } from "./api";
import type {
  Finance,
  Task,
  Project,
  User,
  Client,
  Entry,
  Invoice,
} from "./types";
import { Field, Money, ErrorMessage } from "./components";
import { statuses, label, dateTime, duration } from "./format";
export function FinanceCards({ finance: f }: { finance: Finance }) {
  return (
    <div className="stats finance">
      <article className="stat">
        <span>Worked value · estimate</span>
        <strong>
          <Money value={f.worked_estimate} currency={f.currency} />
        </strong>
        <small>Current rates + completed fixed tasks</small>
      </article>
      <article className="stat">
        <span>Uninvoiced · estimate</span>
        <strong>
          <Money value={f.uninvoiced_estimate} currency={f.currency} />
        </strong>
        <small>Excludes draft reservations</small>
      </article>
      <article className="stat">
        <span>Drafts reserved</span>
        <strong>
          <Money value={f.draft_reserved} currency={f.currency} />
        </strong>
        <small>Not yet an issued liability</small>
      </article>
      <article className="stat">
        <span>Outstanding</span>
        <strong>
          <Money value={f.outstanding} currency={f.currency} />
        </strong>
        <small>Issued total minus received</small>
      </article>
      <article className="stat accent">
        <span>Payments received</span>
        <strong>
          <Money value={f.payments_received} currency={f.currency} />
        </strong>
        <small>Recorded manual payments</small>
      </article>
    </div>
  );
}
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
export function InvoiceSources({
  clients,
  projects,
  tasks,
  entries,
  currency,
}: {
  clients: Client[];
  projects: Project[];
  tasks: Task[];
  entries: Entry[];
  currency: string;
}) {
  const [client, setClient] = useState(""),
    [reserved, setReserved] = useState<Set<string>>(new Set()),
    [ready, setReady] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    all<Invoice>("/invoices")
      .then(async (invoices) => {
        const detail = await Promise.all(
          invoices
            .filter((i) => i.status !== "void")
            .map((i) => api<Invoice>(`/invoices/${i.id}`)),
        );
        setReserved(
          new Set(
            detail.flatMap((i) =>
              (i.lines || []).flatMap((l) => [
                l.source_entry_id || "",
                l.source_task_id || "",
              ]),
            ),
          ),
        );
        setReady(true);
      })
      .catch((e) => setError(e.message));
  }, []);
  const selectedTasks = tasks.filter(
    (t) => projects.find((p) => p.id === t.project_id)?.client_id === client,
  );
  const billable = entries.filter(
    (e) =>
      e.ended_at &&
      e.billable &&
      !e.reserved &&
      selectedTasks.some((t) => t.id === e.task_id && t.billing === "hourly"),
  );
  const fixed = selectedTasks.filter(
    (t) => t.billing === "fixed" && t.status === "done" && !reserved.has(t.id),
  );
  return (
    <>
      <ErrorMessage error={error} />
      <Field title="Client">
        <select
          name="client_id"
          value={client}
          onChange={(e) => setClient(e.target.value)}
          required
        >
          <option value="">Select a client</option>
          {clients.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </Field>
      <p className="small muted">
        Select explicit sources. Prices are saved in the draft and remain frozen
        after issuance. Fixed-price time never adds an hourly charge.
      </p>
      <fieldset key={client}>
        <legend>Completed hourly work</legend>
        {billable.map((e) => (
          <label className="source check" key={e.id}>
            <input type="checkbox" name="entries" value={e.id} />
            <span>
              <strong>{tasks.find((t) => t.id === e.task_id)?.title}</strong>
              <small>
                {dateTime(e.started_at)} · {duration(e.seconds)}
              </small>
            </span>
          </label>
        ))}
        {billable.length === 0 && (
          <p className="small muted">
            No eligible hourly work for this client.
          </p>
        )}
      </fieldset>
      <fieldset key={"fixed" + client}>
        <legend>Finished fixed-price tasks</legend>
        {!ready ? (
          <p>Loading reservations…</p>
        ) : (
          fixed.map((t) => (
            <label className="source check" key={t.id}>
              <input type="checkbox" name="fixed_tasks" value={t.id} />
              <span>
                {t.title} ·{" "}
                <Money value={t.fixed_price || "0"} currency={currency} />
              </span>
            </label>
          ))
        )}
        {ready && fixed.length === 0 && (
          <p className="small muted">No eligible fixed-price tasks.</p>
        )}
      </fieldset>
    </>
  );
}
