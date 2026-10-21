import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type { Rule, User } from "../types";
import { formatDateShort, titleCase } from "../utils";
import { Badge, Button, Card, EmptyState, ErrorNote, Modal, Spinner } from "../components/ui";
import { Icon } from "../components/Icon";

const statusTone: Record<string, "success" | "warning" | "neutral"> = {
  active: "success",
  draft: "warning",
  archived: "neutral",
};

export function Rules({
  user,
  onEdit,
}: {
  user: User;
  onEdit: (ruleId: string | null) => void;
}) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [toArchive, setToArchive] = useState<Rule | null>(null);
  const [archiving, setArchiving] = useState(false);

  const canEdit = user.role === "admin" || user.role === "editor";

  const load = () => {
    setLoading(true);
    api
      .listRules()
      .then(setRules)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load rules"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const filtered = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return rules.filter((rule) => {
      if (statusFilter !== "all" && rule.status !== statusFilter) return false;
      if (!needle) return true;
      return (
        rule.name.toLowerCase().includes(needle) ||
        rule.key.toLowerCase().includes(needle) ||
        rule.document_type.toLowerCase().includes(needle)
      );
    });
  }, [rules, search, statusFilter]);

  const archive = async () => {
    if (!toArchive) return;
    setArchiving(true);
    try {
      await api.archiveRule(toArchive.id);
      setToArchive(null);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to archive rule");
    } finally {
      setArchiving(false);
    }
  };

  if (loading) return <Spinner label="Loading rules…" />;

  return (
    <div className="stack">
      <div className="toolbar">
        <div className="toolbar-left">
          <div className="search-box">
            <Icon name="search" size={16} />
            <input
              className="search-input"
              placeholder="Search rules by name, key or type…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <select
            className="select select-sm"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
        </div>
        {canEdit ? (
          <Button icon="plus" onClick={() => onEdit(null)}>
            New rule
          </Button>
        ) : null}
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {filtered.length === 0 ? (
        <Card>
          <EmptyState
            icon="rules"
            title={rules.length === 0 ? "No coding rules yet" : "No matching rules"}
            description={
              rules.length === 0
                ? "Create a rule to define how part numbers are composed."
                : "Try a different search or status filter."
            }
            action={
              canEdit && rules.length === 0 ? (
                <Button icon="plus" onClick={() => onEdit(null)}>
                  Create the first rule
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <Card padded={false}>
          <div className="table-wrap">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Rule</th>
                  <th>Document type</th>
                  <th>Version</th>
                  <th>Status</th>
                  <th>Updated</th>
                  {canEdit ? <th className="align-right">Actions</th> : null}
                </tr>
              </thead>
              <tbody>
                {filtered.map((rule) => (
                  <tr key={rule.id}>
                    <td>
                      <div className="cell-title">{rule.name}</div>
                      <div className="cell-sub mono">{rule.key}</div>
                    </td>
                    <td>
                      <Badge tone="info">{titleCase(rule.document_type)}</Badge>
                    </td>
                    <td className="mono">v{rule.version}</td>
                    <td>
                      <Badge tone={statusTone[rule.status] ?? "neutral"}>
                        {titleCase(rule.status)}
                      </Badge>
                    </td>
                    <td className="muted">{formatDateShort(rule.created_at)}</td>
                    {canEdit ? (
                      <td className="align-right">
                        <div className="row-actions">
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => onEdit(rule.id)}
                          >
                            Edit
                          </Button>
                          {rule.status === "active" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              icon="trash"
                              onClick={() => setToArchive(rule)}
                            >
                              Archive
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Modal
        open={Boolean(toArchive)}
        title="Archive this rule?"
        onClose={() => setToArchive(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setToArchive(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={archive} loading={archiving}>
              Archive rule
            </Button>
          </>
        }
      >
        <p>
          <strong>{toArchive?.name}</strong> will stop accepting new generations.
          Codes already generated remain valid and searchable.
        </p>
      </Modal>
    </div>
  );
}
