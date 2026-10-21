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
  Field,
  Modal,
  Spinner,
} from "../components/ui";
import { Icon } from "../components/Icon";

const statusTone: Record<string, "success" | "warning" | "neutral" | "danger"> = {
  reserved: "warning",
  committed: "success",
  void: "danger",
};

function parseMetadata(text: string): Record<string, unknown> {
  if (!text.trim()) return {};
  const parsed: unknown = JSON.parse(text);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Metadata must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
}

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
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");
  const [editExternalRef, setEditExternalRef] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editMetadata, setEditMetadata] = useState("");
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

  const openItem = (item: Item) => {
    setSelected(item);
    setEditing(false);
    setConfirmVoid(false);
    setEditError("");
  };

  const startEdit = () => {
    if (!selected) return;
    setEditExternalRef(selected.external_ref ?? "");
    setEditNotes(selected.notes ?? "");
    setEditMetadata(JSON.stringify(selected.payload, null, 2));
    setEditError("");
    setEditing(true);
    setConfirmVoid(false);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditError("");
  };

  const saveItem = async () => {
    if (!selected) return;
    setSaving(true);
    setEditError("");
    let metadata: Record<string, unknown>;
    try {
      metadata = parseMetadata(editMetadata);
    } catch (err) {
      setEditError(
        err instanceof Error ? `Invalid metadata: ${err.message}` : "Invalid metadata JSON.",
      );
      setSaving(false);
      return;
    }
    try {
      const updated = await api.updateItem(selected.id, {
        external_ref: editExternalRef.trim() || null,
        notes: editNotes.trim() || null,
        metadata,
      });
      setSelected(updated);
      setEditing(false);
      load();
    } catch (err) {
      setEditError(err instanceof ApiError ? err.message : "Unable to update the item");
    } finally {
      setSaving(false);
    }
  };

  const voidItem = async () => {
    if (!selected) return;
    setVoiding(true);
    try {
      const updated = await api.voidItem(selected.id);
      setSelected(updated);
      setConfirmVoid(false);
      setEditing(false);
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
                  <tr key={item.id} onClick={() => openItem(item)} className="clickable">
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
          setEditing(false);
          setEditError("");
        }}
        width={640}
        footer={
          selected ? (
            <div className="modal-actions">
              {editing ? (
                <>
                  <Button variant="ghost" onClick={cancelEdit}>
                    Cancel
                  </Button>
                  <Button onClick={saveItem} loading={saving}>
                    Save changes
                  </Button>
                </>
              ) : (
                <>
                  <CopyButton value={selected.code} label="Copy code" />
                  {canEdit && selected.status !== "void" ? (
                    <>
                      <Button variant="secondary" icon="link" onClick={startEdit}>
                        Edit link
                      </Button>
                      {confirmVoid ? (
                        <>
                          <Button variant="ghost" onClick={() => setConfirmVoid(false)}>
                            Cancel
                          </Button>
                          <Button variant="danger" onClick={voidItem} loading={voiding}>
                            Confirm void
                          </Button>
                        </>
                      ) : (
                        <Button
                          variant="danger"
                          icon="trash"
                          onClick={() => setConfirmVoid(true)}
                        >
                          Void code
                        </Button>
                      )}
                    </>
                  ) : null}
                </>
              )}
            </div>
          ) : null
        }
      >
        {selected ? (
          editing ? (
            <div className="detail-stack">
              {editError ? <ErrorNote message={editError} /> : null}
              <div className="detail-code">
                <span>{selected.code}</span>
                <Badge tone={statusTone[selected.status] ?? "neutral"}>
                  {selected.status}
                </Badge>
              </div>
              <div className="warning-note">
                The code and rule version stay immutable. Changing the external
                reference can break an existing PDM/ERP link.
              </div>
              <div className="form-grid">
                <Field
                  label="External reference"
                  hint="Leave empty to unlink. Must be unique across active items."
                  className="span-2"
                  error={editError && editError.includes("external reference") ? editError : undefined}
                >
                  <input
                    className="input mono"
                    value={editExternalRef}
                    maxLength={512}
                    placeholder="PDM:VaultName:1234"
                    onChange={(event) => setEditExternalRef(event.target.value)}
                  />
                </Field>
                <Field label="Notes" className="span-2">
                  <textarea
                    className="textarea"
                    value={editNotes}
                    maxLength={2000}
                    rows={3}
                    placeholder="Optional context for this code"
                    onChange={(event) => setEditNotes(event.target.value)}
                  />
                </Field>
                <Field
                  label="Metadata (JSON)"
                  hint="Replaces the item metadata payload. Generated code and rule version are unchanged."
                  className="span-2"
                >
                  <textarea
                    className="textarea mono"
                    value={editMetadata}
                    rows={10}
                    onChange={(event) => setEditMetadata(event.target.value)}
                  />
                </Field>
              </div>
            </div>
          ) : (
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
                {selected.notes ? (
                  <div className="span-2">
                    <dt>Notes</dt>
                    <dd className="pre-wrap">{selected.notes}</dd>
                  </div>
                ) : null}
                {selected.voided_at ? (
                  <div>
                    <dt>Voided</dt>
                    <dd>{formatDate(selected.voided_at)}</dd>
                  </div>
                ) : null}
              </dl>
              <div>
                <div className="detail-label">Metadata</div>
                <pre className="json-block">{JSON.stringify(selected.payload, null, 2)}</pre>
              </div>
            </div>
          )
        ) : null}
      </Modal>
    </div>
  );
}
