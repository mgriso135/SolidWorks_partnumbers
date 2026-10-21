import { useEffect, useState } from "react";
import { api, getToken, onUnauthorized, setToken } from "./api";
import type { AuthResponse, Page, Rule } from "./types";
import { Layout } from "./components/Layout";
import { Icon } from "./components/Icon";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Generate } from "./pages/Generate";
import { Rules } from "./pages/Rules";
import { RuleEditor } from "./pages/RuleEditor";
import { Items } from "./pages/Items";
import { Audit } from "./pages/Audit";
import { Settings } from "./pages/Settings";

export default function App() {
  const [session, setSession] = useState<AuthResponse | null>(null);
  const [booting, setBooting] = useState(true);
  const [page, setPage] = useState<Page>("dashboard");
  const [ruleId, setRuleId] = useState<string | null>(null);
  const [flash, setFlash] = useState("");

  useEffect(() => {
    onUnauthorized(() => {
      setSession(null);
      setPage("dashboard");
    });
  }, []);

  useEffect(() => {
    if (!getToken()) {
      setBooting(false);
      return;
    }
    api
      .me()
      .then((user) => {
        const token = getToken();
        if (token) setSession({ access_token: token, token_type: "bearer", user });
      })
      .catch(() => setToken(null))
      .finally(() => setBooting(false));
  }, []);

  useEffect(() => {
    if (!flash) return;
    const timer = window.setTimeout(() => setFlash(""), 3200);
    return () => window.clearTimeout(timer);
  }, [flash]);

  const login = (next: AuthResponse) => {
    setToken(next.access_token);
    setSession(next);
    setPage("dashboard");
    setFlash(`Signed in as ${next.user.email}`);
  };

  const logout = () => {
    setToken(null);
    setSession(null);
    setPage("dashboard");
  };

  if (booting) {
    return (
      <div className="boot-screen">
        <div className="brand-mark brand-mark-lg">
          <Icon name="spark" size={22} />
        </div>
        <div className="boot-name">PartCode</div>
        <span className="spinner" />
      </div>
    );
  }

  if (!session) return <Login onLogin={login} />;

  const role = session.user.role;
  const effectivePage: Page =
    (page === "settings" && role !== "admin") ||
    (page === "audit" && role === "viewer")
      ? "dashboard"
      : page;

  const navigate = (target: Page) => {
    setPage(target);
    if (target !== "rule-editor") setRuleId(null);
  };

  const openEditor = (id: string | null) => {
    setRuleId(id);
    setPage("rule-editor");
  };

  const savedRule = (rule: Rule) => {
    setPage("rules");
    setRuleId(null);
    setFlash(`Rule "${rule.name}" saved as v${rule.version}`);
  };

  return (
    <>
      <Layout
        user={session.user}
        page={effectivePage}
        onNavigate={navigate}
        onLogout={logout}
      >
        {effectivePage === "dashboard" ? (
          <Dashboard user={session.user} onNavigate={navigate} />
        ) : null}
        {effectivePage === "generate" ? (
          <Generate user={session.user} onNavigate={navigate} />
        ) : null}
        {effectivePage === "rules" ? (
          <Rules user={session.user} onEdit={openEditor} />
        ) : null}
        {effectivePage === "rule-editor" ? (
          <RuleEditor
            ruleId={ruleId}
            onBack={() => {
              setPage("rules");
              setRuleId(null);
            }}
            onSaved={savedRule}
          />
        ) : null}
        {effectivePage === "items" ? <Items user={session.user} /> : null}
        {effectivePage === "audit" ? <Audit /> : null}
        {effectivePage === "settings" ? (
          <Settings currentUser={session.user} />
        ) : null}
      </Layout>
      {flash ? (
        <div className="toast">
          <Icon name="check" size={16} />
          {flash}
        </div>
      ) : null}
    </>
  );
}
