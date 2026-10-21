import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { AuditEntry, AuditPage } from "../types";
import { formatDate, humanAction } from "../utils";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorNote,
  Modal,
  Spinner,
} from "../components/ui";

const ACTIONS = [
  "auth.login",
  "code.generated",
  "rule.created",
  "rule.updated",
  "rule.archived",
  "item.updated",
  "item.committed",
  "item.voided",
  "user.created",
  "user.updated",
  "api_key.created",
  "api_key.revoked",
];

const ENTITIES = ["item", "rule", "user", "api_key"];

export function Audit() {
  const [data, setData] = useState<AuditPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<AuditEntry | null>(null);
  const limit = 30;

  useEffect(() => {
    setLoading(true);
    setError("");
    api
      .audit({
        action,
        entity_type: entityType,
        limit,
        offset,
      })
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load audit log"))
      .finally(() => setLoading(false));
  }, [action, entityType, offset]);

  return (
    <div className="stack">
      <div className="toolbar">
        <div className="toolbar-left">
          <select
            className="select select-sm"
            value={action}
            onChange={(event) => {
              setAction(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All actions</option>
            {ACTIONS.map((item) => (
              <option key={item} value={item}>
                {humanAction(item)}
              </option>
            ))}
          </select>
          <select
            className="select select-sm"
            value={entityType}
            onChange={(event) => {
              setEntityType(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All entities</option>
            {ENTITIES.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </div>
        <div className="muted small">
          {data ? `${data.total} event${data.total === 1 ? "" : "s"}` : ""}
        </div>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <Spinner label="Loading audit log…" />
      ) : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon="clock"
            title="No audit events"
            description="Activity will appear here as codes are generated and rules change."
          />
        </Card>
      ) : (
        <Card padded={false}>
          <div className="table-wrap">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Action</th>
                  <th>Actor</th>
                  <th>Entity</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((entry) => (
                  <tr key={entry.id} onClick={() => setSelected(entry)} className="clickable">
                    <td className="muted nowrap">{formatDate(entry.created_at)}</td>
                    <td>
                      <span className="action-label">{humanAction(entry.action)}</span>
                    </td>
                    <td>
                      <Badge tone={entry.actor_type === "api_key" ? "info" : "neutral"}>
                        {entry.actor_type}
                      </Badge>
                    </td>
                    <td className="muted">
                      {entry.entity_type}
                      {entry.entity_id ? (
                        <span className="mono small"> · {entry.entity_id.slice(0, 8)}</span>
                      ) : null}
                    </td>
                    <td className="muted truncate" title={JSON.stringify(entry.details)}>
                      {detailsSummary(entry)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="pagination">
            <span className="muted small">
              Showing {offset + 1}–{Math.min(offset + limit, data.total)} of {data.total}
            </span>
            <div className="row-actions">
              <Button
                variant="secondary"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={offset + limit >= data.total}
                onClick={() => setOffset(offset + limit)}
              >
                Next
              </Button>
            </div>
          </div>
        </Card>
      )}

      <Modal
        open={Boolean(selected)}
        title="Audit event"
        onClose={() => setSelected(null)}
        width={620}
      >
        {selected ? (
          <div className="detail-stack">
            <dl className="detail-list">
              <div>
                <dt>Action</dt>
                <dd>{humanAction(selected.action)}</dd>
              </div>
              <div>
                <dt>When</dt>
                <dd>{formatDate(selected.created_at)}</dd>
              </div>
              <div>
                <dt>Actor</dt>
                <dd>
                  {selected.actor_type} · <span className="mono">{selected.actor_id ?? "—"}</span>
                </dd>
              </div>
              <div>
                <dt>Entity</dt>
                <dd className="mono">
                  {selected.entity_type} · {selected.entity_id ?? "—"}
                </dd>
              </div>
              <div>
                <dt>IP address</dt>
                <dd className="mono">{selected.ip ?? "—"}</dd>
              </div>
            </dl>
            <div>
              <div className="detail-label">Details</div>
              <pre className="json-block">{JSON.stringify(selected.details, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}

function detailsSummary(entry: AuditEntry): string {
  const details = entry.details ?? {};
  if (typeof details.code === "string") return details.code;
  if (typeof details.key === "string") return `${details.key} v${details.version ?? "?"}`;
  if (typeof details.email === "string") return details.email;
  if (typeof details.name === "string") return details.name;
  return Object.keys(details).length ? JSON.stringify(details) : "—";
}
