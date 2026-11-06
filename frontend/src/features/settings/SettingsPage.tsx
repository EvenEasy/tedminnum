import { checked, dateTime, formData, text } from "../../shared/format";
import { Field, Status } from "../../shared/ui";
import { authApi } from "../auth/api";
import { settingsApi } from "./api";

import type { WorkspaceController } from "../../app/useWorkspaceController";
export function SettingsPage(
  props: Pick<
    WorkspaceController,
    | "audits"
    | "busy"
    | "deliveries"
    | "detail"
    | "hookSecret"
    | "hooks"
    | "isAdmin"
    | "mutate"
    | "setEditor"
    | "setError"
    | "setHookSecret"
    | "setTheme"
    | "setUser"
    | "switchUser"
    | "theme"
    | "user"
    | "users"
    | "workspace"
  >,
) {
  const {
    audits,
    busy,
    deliveries,
    detail,
    hookSecret,
    hooks,
    isAdmin,
    mutate,
    setEditor,
    setError,
    setHookSecret,
    setTheme,
    setUser,
    switchUser,
    theme,
    user,
    users,
    workspace,
  } = props;

  return (
    <div className="settings-grid">
      <section className="panel">
        <div className="panel-head">
          <h2>Focus & reminders</h2>
          <button
            type="button"
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            Switch to {theme === "dark" ? "light" : "dark"} appearance
          </button>
        </div>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const f = formData(e);
            const prefs = {
              work_minutes: Number(text(f, "work_minutes")),
              short_break: Number(text(f, "short_break")),
              long_break: Number(text(f, "long_break")),
              notifications: checked(f, "notifications"),
            };
            if (prefs.notifications && "Notification" in window) {
              const permission = await Notification.requestPermission();
              if (permission !== "granted") {
                setError(
                  "Browser notifications were not granted. In-app reminders remain active.",
                );
                prefs.notifications = false;
              }
            }
            const r = await mutate(
              () => settingsApi.preferences(prefs),
              "Focus preferences saved",
            );
            if (r) setUser({ ...user, ...prefs });
          }}
        >
          <div className="form-grid">
            <Field title="Focus minutes">
              <input
                name="work_minutes"
                type="number"
                min="1"
                max="180"
                defaultValue={user.work_minutes}
                required
              />
            </Field>
            <Field title="Short break minutes">
              <input
                name="short_break"
                type="number"
                min="1"
                max="60"
                defaultValue={user.short_break}
                required
              />
            </Field>
            <Field title="Long break minutes">
              <input
                name="long_break"
                type="number"
                min="1"
                max="120"
                defaultValue={user.long_break}
                required
              />
            </Field>
          </div>
          <label className="check">
            <input
              name="notifications"
              type="checkbox"
              defaultChecked={user.notifications}
            />
            Browser notifications
          </label>
          <p className="small muted">
            Reminders work while this app is open. Timers continue until you
            stop them. Choose a short or long break when starting a break
            session.
          </p>
          <button className="primary" disabled={busy}>
            Save preferences
          </button>
        </form>
      </section>
      <section className="panel">
        <h2>Change your password</h2>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const f = formData(e);
            if (
              await mutate(
                () =>
                  authApi.password({
                    current_password: text(f, "current"),
                    new_password: text(f, "new"),
                  }),
                "Password changed. Please sign in again.",
              )
            )
              switchUser(null);
          }}
        >
          <Field title="Current password">
            <input
              name="current"
              type="password"
              autoComplete="current-password"
              required
            />
          </Field>
          <Field title="New password">
            <input
              name="new"
              type="password"
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              required
            />
          </Field>
          <button disabled={busy}>Change password & sign out</button>
        </form>
      </section>
      {isAdmin && (
        <>
          <section className="panel">
            <h2>Workspace</h2>
            <form
              key={workspace.currency + workspace.name}
              onSubmit={(e) => {
                e.preventDefault();
                const f = formData(e);
                void mutate(
                  () =>
                    settingsApi.workspace({
                      name: text(f, "name"),
                      currency: text(f, "currency"),
                    }),
                  "Workspace saved",
                );
              }}
            >
              <Field title="Name">
                <input
                  name="name"
                  defaultValue={workspace.name}
                  required
                  maxLength={200}
                />
              </Field>
              <Field title="Currency">
                <select name="currency" defaultValue={workspace.currency}>
                  {["USD", "EUR", "GBP", "UAH", "CAD", "PLN", "CHF", "AUD"].map(
                    (c) => (
                      <option key={c}>{c}</option>
                    ),
                  )}
                </select>
              </Field>
              <p className="small muted">
                Currency is locked once clients or invoices exist.
              </p>
              <button disabled={busy}>Save workspace</button>
            </form>
          </section>
          <section className="panel">
            <div className="panel-head">
              <h2>People & access</h2>
              <button onClick={() => setEditor({ kind: "user" })}>
                ＋ Add person
              </button>
            </div>
            {users.map((u) => (
              <div className="user-row" key={u.id}>
                <div>
                  <strong>{u.name}</strong>
                  <small>{u.email}</small>
                </div>
                <select
                  aria-label={`Role for ${u.name}`}
                  value={u.role}
                  disabled={busy}
                  onChange={(e) => {
                    const role = e.target.value;
                    if (
                      confirm(
                        `Change ${u.name}'s role to ${role}? Existing sessions will be revoked.`,
                      )
                    )
                      void mutate(
                        () =>
                          settingsApi.updateUser(u.id, {
                            role,
                            active: u.active,
                          }),
                        "User updated",
                      );
                  }}
                >
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      confirm(
                        `${u.active ? "Disable" : "Enable"} ${u.name}? Existing sessions will be revoked.`,
                      )
                    )
                      void mutate(
                        () =>
                          settingsApi.updateUser(u.id, {
                            role: u.role,
                            active: !u.active,
                          }),
                        "User updated",
                      );
                  }}
                >
                  {u.active ? "Disable" : "Enable"}
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    setEditor({ kind: "reset", item: u });
                  }}
                >
                  Reset password
                </button>
              </div>
            ))}
          </section>
          <section className="panel full">
            <h2>Outgoing webhooks</h2>
            <p className="small muted">
              HTTPS hosts must be allowed in WEBHOOK_HOSTS. Secrets are shown
              once. Signed events retry up to six times.
            </p>
            <form
              className="inline-form"
              onSubmit={async (e) => {
                e.preventDefault();
                const f = formData(e);
                await mutate(async () => {
                  const h = await settingsApi.createHook({
                    url: text(f, "url"),
                  });
                  setHookSecret(h.secret);
                }, "Webhook created");
              }}
            >
              <input
                name="url"
                aria-label="Webhook HTTPS URL"
                type="url"
                placeholder="https://allowed-host.example/events"
                required
              />
              <button disabled={busy}>Add endpoint</button>
            </form>
            {hookSecret && (
              <div className="alert success">
                <strong>Copy this secret now:</strong>
                <code className="secret">{hookSecret}</code>
                <button onClick={() => setHookSecret("")}>Hide</button>
              </div>
            )}
            {hooks.map((h) => (
              <div className="user-row" key={h.id}>
                <span className="break-text">{h.url}</span>
                <Status value={h.enabled ? "enabled" : "disabled"} />
                <button
                  disabled={busy}
                  onClick={() =>
                    void mutate(
                      () => settingsApi.toggleHook(h.id, !h.enabled),
                      "Webhook updated",
                    )
                  }
                >
                  {h.enabled ? "Disable" : "Enable"}
                </button>
                <button
                  disabled={busy}
                  onClick={() => {
                    if (
                      confirm(
                        "Rotate this secret? Update your receiver before new deliveries.",
                      )
                    )
                      void mutate(async () => {
                        const r = await settingsApi.rotateHook(h.id, h.enabled);
                        setHookSecret(r.secret);
                      }, "Secret rotated");
                  }}
                >
                  Rotate secret
                </button>
              </div>
            ))}
            {deliveries.slice(0, 20).map((d) => (
              <div className="activity" key={d.id}>
                <div>
                  <strong>{d.event}</strong>
                  <small>{d.id}</small>
                </div>
                <span>
                  {d.delivered_at
                    ? "Delivered"
                    : d.attempts >= 6
                      ? "Exhausted"
                      : "Pending"}{" "}
                  · {d.attempts} attempts · {d.status_code ?? "—"}
                </span>
              </div>
            ))}
          </section>
          <section className="panel full">
            <h2>Audit history</h2>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Action</th>
                    <th>Object</th>
                    <th>Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {audits.map((a) => (
                    <tr key={a.id}>
                      <td>{dateTime(a.created_at)}</td>
                      <td>{a.action}</td>
                      <td className="mono small">{a.object_id}</td>
                      <td>{a.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
