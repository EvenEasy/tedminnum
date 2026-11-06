import { useEffect, useState } from "react";
import { dateTime, duration } from "../../shared/format";
import type { Client, Entry, Project, Task } from "../../shared/types";
import { ErrorMessage, Field, Money } from "../../shared/ui";
import { billingApi } from "./api";
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
    billingApi
      .list()
      .then(async (invoices) => {
        const detail = await Promise.all(
          invoices
            .filter((i) => i.status !== "void")
            .map((i) => billingApi.invoice(i.id)),
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
