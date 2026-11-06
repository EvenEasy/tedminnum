import type React from "react";
import { api, uid } from "./api";
import type {
  Editor,
  Client,
  Project,
  Task,
  Entry,
  User,
  Workspace,
} from "./types";
import { formData, text, nullable, checked, localInput } from "./format";
import { Modal, Field, ErrorMessage } from "./components";
import { TaskFields, InvoiceSources } from "./work-forms";
export function EditorDialog({
  editor,
  error,
  busy,
  mutate,
  onClose,
  clients,
  projects,
  tasks,
  entries,
  users,
  workspace,
  invoiceKey,
}: {
  editor: Editor;
  error: string;
  busy: boolean;
  mutate: (
    action: () => Promise<unknown>,
    message?: string,
  ) => Promise<boolean>;
  onClose: () => void;
  clients: Client[];
  projects: Project[];
  tasks: Task[];
  entries: Entry[];
  users: User[];
  workspace: Workspace;
  invoiceKey: React.RefObject<string>;
}) {
  return (
    <Modal
      title={`${"item" in editor && editor.item ? "Edit" : "New"} ${editor.kind === "time" ? "time entry" : editor.kind}`}
      onClose={() => onClose()}
    >
      <ErrorMessage error={error} />
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = formData(e);
          let ok = false;
          if (editor.kind === "client") {
            const data = { name: text(f, "name"), rate: text(f, "rate") };
            ok = await mutate(
              () =>
                api(
                  editor.item ? `/clients/${editor.item.id}` : "/clients",
                  editor.item ? "PATCH" : "POST",
                  data,
                ),
              "Client saved",
            );
          }
          if (editor.kind === "project") {
            const data = {
              name: text(f, "name"),
              rate: nullable(f, "rate"),
              member_ids: f.getAll("members"),
            };
            ok = await mutate(
              () =>
                api(
                  editor.item ? `/projects/${editor.item.id}` : "/projects",
                  editor.item ? "PATCH" : "POST",
                  editor.item
                    ? data
                    : { ...data, client_id: text(f, "client_id") },
                ),
              "Project saved",
            );
          }
          if (editor.kind === "task") {
            const data = {
              title: text(f, "title"),
              description: text(f, "description"),
              status: text(f, "status"),
              priority: text(f, "priority"),
              due_date: nullable(f, "due_date"),
              estimate_minutes:
                nullable(f, "estimate_minutes") === null
                  ? null
                  : Number(text(f, "estimate_minutes")),
              position: Number(text(f, "position")),
              billing: text(f, "billing"),
              rate: nullable(f, "rate"),
              fixed_price: nullable(f, "fixed_price"),
              assignee_ids: f.getAll("assignees"),
            };
            ok = await mutate(
              () =>
                api(
                  editor.item ? `/tasks/${editor.item.id}` : "/tasks",
                  editor.item ? "PATCH" : "POST",
                  editor.item
                    ? { ...data, version: editor.item.version }
                    : { ...data, project_id: text(f, "project_id") },
                ),
              "Task saved",
            );
          }
          if (editor.kind === "time") {
            ok = await mutate(
              () =>
                api(`/time/${editor.item.id}`, "PATCH", {
                  started_at: new Date(text(f, "started_at")).toISOString(),
                  ended_at: new Date(text(f, "ended_at")).toISOString(),
                  billable: checked(f, "billable"),
                  note: text(f, "note"),
                }),
              "Time adjusted and audited",
            );
          }
          if (editor.kind === "user") {
            ok = await mutate(
              () =>
                api("/users", "POST", {
                  name: text(f, "name"),
                  email: text(f, "email"),
                  password: text(f, "password"),
                  role: text(f, "role"),
                }),
              "Account created",
            );
          }
          if (editor.kind === "reset") {
            ok = await mutate(
              () =>
                api(`/users/${editor.item.id}`, "PATCH", {
                  role: editor.item.role,
                  active: editor.item.active,
                  password: text(f, "password"),
                }),
              "Password reset; sessions revoked",
            );
          }
          if (editor.kind === "invoice") {
            ok = await mutate(
              () =>
                api("/invoices", "POST", {
                  client_id: text(f, "client_id"),
                  request_key: invoiceKey.current,
                  entry_ids: f.getAll("entries"),
                  task_ids: f.getAll("fixed_tasks"),
                }),
              "Draft created; selected work reserved",
            );
            if (ok) invoiceKey.current = uid();
          }
          if (ok) onClose();
        }}
      >
        {editor.kind === "client" && (
          <>
            <Field title="Client name">
              <input
                name="name"
                required
                maxLength={200}
                defaultValue={editor.item?.name}
              />
            </Field>
            <Field title={`Default hourly rate (${workspace.currency})`}>
              <input
                name="rate"
                type="number"
                min="0"
                step="0.01"
                max="9999999999"
                required
                defaultValue={editor.item?.rate || "0"}
              />
            </Field>
          </>
        )}
        {editor.kind === "project" && (
          <>
            <Field title="Project name">
              <input
                name="name"
                required
                maxLength={200}
                defaultValue={editor.item?.name}
              />
            </Field>
            {!editor.item && (
              <Field title="Client">
                <select name="client_id" required>
                  <option value="">Select a client</option>
                  {clients.map((c) => (
                    <option value={c.id} key={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field title="Hourly rate override (blank inherits client)">
              <input
                name="rate"
                type="number"
                min="0"
                step="0.01"
                defaultValue={editor.item?.rate || ""}
              />
            </Field>
            <fieldset>
              <legend>Project members</legend>
              {users
                .filter((u) => u.active)
                .map((u) => (
                  <label className="check" key={u.id}>
                    <input
                      type="checkbox"
                      name="members"
                      value={u.id}
                      defaultChecked={
                        editor.kind === "project" &&
                        editor.item?.member_ids?.includes(u.id)
                      }
                    />
                    {u.name}
                  </label>
                ))}
            </fieldset>
          </>
        )}
        {editor.kind === "task" && (
          <TaskFields
            item={editor.item}
            projects={projects}
            users={users}
            currency={workspace.currency}
          />
        )}
        {editor.kind === "time" && (
          <>
            <p className="small muted">
              Use your local time. The server stores UTC. An adjustment replaces
              the interval and clears its recorded pauses. Overlapping and
              invoiced time cannot be changed.
            </p>
            <Field title="Started">
              <input
                type="datetime-local"
                step="1"
                name="started_at"
                defaultValue={localInput(editor.item.started_at)}
                required
              />
            </Field>
            <Field title="Ended">
              <input
                type="datetime-local"
                step="1"
                name="ended_at"
                defaultValue={localInput(editor.item.ended_at!)}
                required
              />
            </Field>
            <label className="check">
              <input
                type="checkbox"
                name="billable"
                defaultChecked={editor.item.billable}
              />
              Billable (work with a billable task only)
            </label>
            <Field title="Note">
              <textarea
                name="note"
                maxLength={2000}
                defaultValue={editor.item.note}
              />
            </Field>
          </>
        )}
        {editor.kind === "user" && (
          <>
            <Field title="Full name">
              <input name="name" required maxLength={200} />
            </Field>
            <Field title="Email">
              <input name="email" type="email" required maxLength={254} />
            </Field>
            <Field title="Temporary password (12+ characters)">
              <input
                name="password"
                type="password"
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </Field>
            <Field title="Role">
              <select name="role">
                <option value="member">Member</option>
                <option value="admin">Administrator</option>
              </select>
            </Field>
          </>
        )}
        {editor.kind === "reset" && (
          <>
            <p>
              Reset the password for {editor.item.name}. Existing sessions will
              be revoked.
            </p>
            <Field title="New password">
              <input
                name="password"
                type="password"
                minLength={12}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </Field>
          </>
        )}
        {editor.kind === "invoice" && (
          <InvoiceSources
            clients={clients}
            projects={projects}
            tasks={tasks}
            entries={entries}
            currency={workspace.currency}
          />
        )}
        <div className="form-actions">
          <button type="button" onClick={() => onClose()}>
            Cancel
          </button>
          <button className="primary" disabled={busy}>
            {busy
              ? "Saving…"
              : editor.kind === "invoice"
                ? "Create draft"
                : "Save"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
