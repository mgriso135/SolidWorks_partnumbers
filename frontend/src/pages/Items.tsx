import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { Item, ItemPage, User } from "../types";
import { formatDate, timeAgo } from "../utils";
import {
  Badge,
  Button,
  Card,
  CopyButton,
  EmptyState,
  ErrorNote,
  Modal,
  Spinner,
} from "../components/ui";
import { Icon } from "../components/Icon";

const statusTone: Record<string, "success" | "warning" | "neutral" | "danger"> = {
  reserved: "warning",
  committed: "success",
  void: "danger",
};

export function Items({ user }: { user: User }) {
  const [data, setData] = useState<ItemPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Item | null>(null);
  const [confirmVoid, setConfirmVoid] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const limit = 25;

  const canEdit = user.role === "admin" || user.role === "editor";

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebounced(search);
      setOffset(0);
    }, 280);
    return () => window.clearTimeout(timer);
  }, [search]);

  const load = () => {
    setLoading(true);
    setError("");
    api
      .listItems({
        q: debounced,
        status_filter: statusFilter,
        limit,
        offset,
      })
      .then(setData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load items"))
      .finally(() => setLoading(false));
  };

  useEffect(load, [debounced, statusFilter, offset]);

  const voidItem = async () => {
    if (!selected) return;
    setVoiding(true);
    try {
      const updated = await api.voidItem(selected.id);
      setSelected(updated);
      setConfirmVoid(false);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to void the code");
    } finally {
      setVoiding(false);
    }
  };

  return (
    <div className="stack">
      <div className="toolbar">
        <div className="toolbar-left">
          <div className="search-box">
            <Icon name="search" size={16} />
            <input
              className="search-input"
              placeholder="Search by code or external reference…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <select
            className="select select-sm"
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">All statuses</option>
            <option value="reserved">Reserved</option>
            <option value="committed">Committed</option>
            <option value="void">Void</option>
          </select>
        </div>
        <div className="muted small">
          {data ? `${data.total} code${data.total === 1 ? "" : "s"}` : ""}
        </div>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {loading ? (
        <Spinner label="Loading code registry…" />
      ) : !data || data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon="box"
            title={debounced ? "No matching codes" : "No codes yet"}
            description={
              debounced
                ? "Try a different search term or status."
                : "Codes generated from the web app or a PDM connector will appear here."
            }
          />
        </Card>
      ) : (
        <Card padded={false}>
          <div className="table-wrap">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Rule</th>
                  <th>Status</th>
                  <th>Source</th>
                  <th>External reference</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((item) => (
                  <tr key={item.id} onClick={() => setSelected(item)} className="clickable">
                    <td>
                      <span className="code-inline">{item.code}</span>
                    </td>
                    <td>
                      <div className="cell-sub mono">{item.rule_key}</div>
                      <div className="cell-sub">v{item.rule_version}</div>
                    </td>
                    <td>
                      <Badge tone={statusTone[item.status] ?? "neutral"}>
                        {item.status}
                      </Badge>
                    </td>
                    <td>
                      <Badge tone="neutral">{item.source}</Badge>
                    </td>
                    <td className="muted mono truncate" title={item.external_ref ?? ""}>
                      {item.external_ref ?? "—"}
                    </td>
                    <td className="muted">{timeAgo(item.created_at)}</td>
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
        title="Code details"
        onClose={() => {
          setSelected(null);
          setConfirmVoid(false);
        }}
        width={640}
        footer={
          selected ? (
            <div className="modal-actions">
              <CopyButton value={selected.code} label="Copy code" />
              {canEdit && selected.status !== "void" ? (
                confirmVoid ? (
                  <>
                    <Button variant="ghost" onClick={() => setConfirmVoid(false)}>
                      Cancel
                    </Button>
                    <Button variant="danger" onClick={voidItem} loading={voiding}>
                      Confirm void
                    </Button>
                  </>
                ) : (
                  <Button variant="danger" icon="trash" onClick={() => setConfirmVoid(true)}>
                    Void code
                  </Button>
                )
              ) : null}
            </div>
          ) : null
        }
      >
        {selected ? (
          <div className="detail-stack">
            {error ? <ErrorNote message={error} /> : null}
            <div className="detail-code">
              <span>{selected.code}</span>
              <Badge tone={statusTone[selected.status] ?? "neutral"}>
                {selected.status}
              </Badge>
            </div>
            {confirmVoid ? (
              <div className="warning-note">
                Voiding keeps the code for audit but marks it as unusable. This cannot
                be undone.
              </div>
            ) : null}
            <dl className="detail-list">
              <div>
                <dt>Rule</dt>
                <dd className="mono">
                  {selected.rule_key} · v{selected.rule_version}
                </dd>
              </div>
              <div>
                <dt>Source</dt>
                <dd>{selected.source}</dd>
              </div>
              <div>
                <dt>Created</dt>
                <dd>{formatDate(selected.created_at)}</dd>
              </div>
              <div>
                <dt>External reference</dt>
                <dd className="mono break-all">{selected.external_ref ?? "—"}</dd>
              </div>
              {selected.voided_at ? (
                <div>
                  <dt>Voided</dt>
                  <dd>{formatDate(selected.voided_at)}</dd>
                </div>
              ) : null}
            </dl>
            <div>
              <div className="detail-label">Attributes</div>
              <pre className="json-block">{JSON.stringify(selected.payload, null, 2)}</pre>
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
