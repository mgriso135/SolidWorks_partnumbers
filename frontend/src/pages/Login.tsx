import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import type { AuthResponse } from "../types";
import { Button, ErrorNote } from "../components/ui";
import { Icon } from "../components/Icon";

const DEMO = [
  { email: "admin@demo.local", password: "Admin123!", role: "Admin" },
  { email: "editor@demo.local", password: "Editor123!", role: "Editor" },
  { email: "viewer@demo.local", password: "Viewer123!", role: "Viewer" },
];

export function Login({ onLogin }: { onLogin: (session: AuthResponse) => void }) {
  const [email, setEmail] = useState("admin@demo.local");
  const [password, setPassword] = useState("Admin123!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const session = await api.login(email, password);
      onLogin(session);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to sign in");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-panel">
        <div className="login-brand">
          <div className="brand-mark brand-mark-lg">
            <Icon name="spark" size={22} />
          </div>
          <span>PartCode</span>
        </div>
        <h2>One numbering standard. Every tool.</h2>
        <p className="login-copy">
          Central rules for SolidWorks, PDM, ERP and Office. Generate unique,
          meaningful codes where engineers already work.
        </p>
        <ul className="login-features">
          <li>
            <Icon name="rules" size={16} />
            Versioned coding rules, editable without a release
          </li>
          <li>
            <Icon name="shield" size={16} />
            Duplicate prevention and atomic counters
          </li>
          <li>
            <Icon name="link" size={16} />
            REST API and API keys for PDM / ERP connectors
          </li>
          <li>
            <Icon name="clock" size={16} />
            Full audit trail for every generated code
          </li>
        </ul>
        <div className="login-footnote">Demo environment · PartCode 1.0</div>
      </div>

      <div className="login-form-panel">
        <div className="login-form">
          <div className="login-form-head">
            <h1>Sign in</h1>
            <p>Use a demo account or your company credentials.</p>
          </div>
          <form onSubmit={submit}>
            <label className="field">
              <span className="field-label">Email</span>
              <input
                className="input"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span className="field-label">Password</span>
              <input
                className="input"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error ? <ErrorNote message={error} /> : null}
            <Button type="submit" loading={loading} className="login-submit">
              Sign in
            </Button>
          </form>

          <div className="demo-box">
            <div className="demo-head">
              <Icon name="keyboard" size={15} />
              Demo accounts
            </div>
            {DEMO.map((account) => (
              <button
                key={account.email}
                type="button"
                className="demo-row"
                onClick={() => {
                  setEmail(account.email);
                  setPassword(account.password);
                }}
              >
                <span>{account.role}</span>
                <code>{account.email}</code>
                <span className="demo-pass">{account.password}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
