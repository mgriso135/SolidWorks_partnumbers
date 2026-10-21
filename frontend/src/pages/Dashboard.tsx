import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { DashboardStats, Page, User } from "../types";
import { humanAction, timeAgo, titleCase } from "../utils";
import { Badge, Button, Card, EmptyState, Spinner } from "../components/ui";
import { Icon } from "../components/Icon";

export function Dashboard({
  user,
  onNavigate,
}: {
  user: User;
  onNavigate: (page: Page) => void;
}) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .stats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load stats");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <Card><EmptyState icon="alert" title="Dashboard unavailable" description={error} /></Card>;
  }
  if (!stats) return <Spinner label="Loading dashboard…" />;

  const maxSource = Math.max(1, ...Object.values(stats.by_source));
  const canEdit = user.role === "admin" || user.role === "editor";

  return (
    <div className="stack-lg">
      <div className="hero-card">
        <div>
          <div className="eyebrow">
            <Icon name="spark" size={14} /> Coding workspace
          </div>
          <h2>Welcome back</h2>
          <p>
            {stats.items_today} code{stats.items_today === 1 ? "" : "s"} generated today ·{" "}
            {stats.active_rules} active rule{stats.active_rules === 1 ? "" : "s"}
          </p>
        </div>
        <div className="hero-actions">
          <Button icon="spark" onClick={() => onNavigate("generate")}>
            Generate code
          </Button>
          {canEdit ? (
            <Button variant="secondary" icon="plus" onClick={() => onNavigate("rules")}>
              Manage rules
            </Button>
          ) : null}
        </div>
      </div>

      <div className="stat-grid">
        <StatCard label="Active rules" value={stats.active_rules} icon="rules" tone="brand" />
        <StatCard label="Codes total" value={stats.items_total} icon="box" tone="neutral" />
        <StatCard label="Last 30 days" value={stats.items_30d} icon="clock" tone="info" />
        <StatCard label="Generated today" value={stats.items_today} icon="spark" tone="success" />
      </div>

      <div className="dashboard-grid">
        <Card className="dashboard-main">
          <div className="card-head">
            <div>
              <h3>Recent codes</h3>
              <p>Latest reservations across every rule.</p>
            </div>
            <Button variant="ghost" size="sm" onClick={() => onNavigate("items")}>
              View registry <Icon name="chevronRight" size={14} />
            </Button>
          </div>
          {stats.recent_items.length === 0 ? (
            <EmptyState
              icon="box"
              title="No codes yet"
              description="Generate the first code to see it here."
              action={
                <Button size="sm" onClick={() => onNavigate("generate")}>
                  Generate a code
                </Button>
              }
            />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Rule</th>
                    <th>Source</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.recent_items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <span className="code-inline">{item.code}</span>
                      </td>
                      <td className="muted">{item.rule_key}</td>
                      <td>
                        <Badge tone="neutral">{item.source}</Badge>
                      </td>
                      <td className="muted">{timeAgo(item.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="dashboard-side">
          <div className="card-head">
            <div>
              <h3>Codes by source</h3>
              <p>Where codes are being created.</p>
            </div>
          </div>
          {Object.keys(stats.by_source).length === 0 ? (
            <p className="muted">No activity yet.</p>
          ) : (
            <div className="source-bars">
              {Object.entries(stats.by_source)
                .sort(([, a], [, b]) => b - a)
                .map(([source, count]) => (
                  <div className="source-row" key={source}>
                    <div className="source-row-head">
                      <span>{titleCase(source)}</span>
                      <strong>{count}</strong>
                    </div>
                    <div className="bar">
                      <div className="bar-fill" style={{ width: `${(count / maxSource) * 100}%` }} />
                    </div>
                  </div>
                ))}
            </div>
          )}
        </Card>
      </div>

      <Card>
        <div className="card-head">
          <div>
            <h3>Recent activity</h3>
            <p>Rule changes, generations and sign-ins.</p>
          </div>
          {user.role !== "viewer" ? (
            <Button variant="ghost" size="sm" onClick={() => onNavigate("audit")}>
              Open audit log <Icon name="chevronRight" size={14} />
            </Button>
          ) : null}
        </div>
        {stats.recent_audit.length === 0 ? (
          <p className="muted">No activity recorded yet.</p>
        ) : (
          <ul className="activity-list">
            {stats.recent_audit.map((entry) => (
              <li key={entry.id}>
                <span className="activity-dot" />
                <div className="activity-body">
                  <div>
                    <strong>{humanAction(entry.action)}</strong>
                    {entry.details?.code ? (
                      <span className="code-inline code-inline-sm">{String(entry.details.code)}</span>
                    ) : null}
                  </div>
                  <span className="muted">
                    {entry.actor_type === "api_key" ? "API key" : "User"} ·{" "}
                    {timeAgo(entry.created_at)}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: number;
  icon: "rules" | "box" | "clock" | "spark";
  tone: "brand" | "neutral" | "info" | "success";
}) {
  return (
    <div className={`stat-card stat-${tone}`}>
      <div className="stat-icon">
        <Icon name={icon} size={18} />
      </div>
      <div>
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}
