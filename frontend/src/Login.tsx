import { useState } from "react";
import { api, setCSRF } from "./api";
import type { User } from "./types";
import { formData, text } from "./format";
import { Field, ErrorMessage } from "./components";
export function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main className="login">
      <div className="login-intro">
        <div className="brandmark">t.</div>
        <p className="eyebrow">YOUR WORK, IN ONE PLACE</p>
        <h1>
          A little more focus.
          <br />A lot more clarity.
        </h1>
        <p>
          Keep projects moving, make time count,
          <br />
          and close the loop on your work.
        </p>
      </div>
      <form
        className="login-card"
        onSubmit={async (e) => {
          e.preventDefault();
          const f = formData(e);
          setBusy(true);
          setError("");
          try {
            const r = await api<{ user: User; csrf: string }>(
              "/auth/login",
              "POST",
              { email: text(f, "email"), password: text(f, "password") },
            );
            setCSRF(r.csrf);
            onLogin(r.user);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <p className="eyebrow">TEDMINNUM</p>
        <h2>Welcome back</h2>
        <p className="muted">Sign in to your workspace.</p>
        <ErrorMessage error={error} />
        <Field title="Email">
          <input
            name="email"
            type="email"
            autoComplete="username"
            required
            autoFocus
          />
        </Field>
        <Field title="Password">
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            maxLength={128}
            required
          />
        </Field>
        <button className="primary wide" disabled={busy}>
          {busy ? "Signing in…" : "Sign in →"}
        </button>
        <p className="small muted">
          Accounts are created by your workspace administrator.
        </p>
      </form>
    </main>
  );
}
