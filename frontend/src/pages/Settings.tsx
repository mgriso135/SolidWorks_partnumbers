import { useEffect, useState } from "react";
import { api, ApiError } from "../api";
import type { ApiKey, ApiKeyCreated, User } from "../types";
import { formatDate, timeAgo, titleCase } from "../utils";
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

type Tab = "users" | "keys";

export function Settings({ currentUser }: { currentUser: User }) {
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<User[]>([]);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const [userModal, setUserModal] = useState(false);
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("viewer");
  const [savingUser, setSavingUser] = useState(false);

  const [keyModal, setKeyModal] = useState(false);
  const [keyName, setKeyName] = useState("");
  const [creatingKey, setCreatingKey] = useState(false);
  const [createdKey, setCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [toRevoke, setToRevoke] = useState<ApiKey | null>(null);
  const [revoking, setRevoking] = useState(false);

  const load = () => {
    setLoading(true);
    setError("");
    Promise.all([api.listUsers(), api.listApiKeys()])
      .then(([userList, keyList]) => {
        setUsers(userList);
        setKeys(keyList);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Unable to load settings"))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const createUser = async () => {
    setSavingUser(true);
    setError("");
    try {
      const created = await api.createUser({
        email: newEmail.trim(),
        password: newPassword,
        role: newRole,
      });
      setUsers((current) => [...current, created]);
      setUserModal(false);
      setNewEmail("");
      setNewPassword("");
      setNewRole("viewer");
      setNotice(`User ${created.email} created`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create user");
    } finally {
      setSavingUser(false);
    }
  };

  const patchUser = async (target: User, patch: { role?: string; active?: boolean }) => {
    setError("");
    try {
      const updated = await api.updateUser(target.id, patch);
      setUsers((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to update user");
    }
  };

  const createKey = async () => {
    setCreatingKey(true);
    setError("");
    try {
      const created = await api.createApiKey(keyName.trim());
      setCreatedKey(created);
      setKeys((current) => [created, ...current]);
      setKeyName("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to create API key");
    } finally {
      setCreatingKey(false);
    }
  };

  const revokeKey = async () => {
    if (!toRevoke) return;
    setRevoking(true);
    try {
      const updated = await api.revokeApiKey(toRevoke.id);
      setKeys((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setToRevoke(null);
      setNotice(`API key ${updated.prefix} revoked`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to revoke API key");
    } finally {
      setRevoking(false);
    }
  };

  if (loading) return <Spinner label="Loading settings…" />;

  return (
    <div className="stack">
      <div className="tabs">
        <button className={`tab${tab === "users" ? " active" : ""}`} onClick={() => setTab("users")}>
          <Icon name="user" size={15} /> Users
        </button>
        <button className={`tab${tab === "keys" ? " active" : ""}`} onClick={() => setTab("keys")}>
          <Icon name="key" size={15} /> API keys
        </button>
      </div>

      {error ? <ErrorNote message={error} /> : null}
      {notice ? (
        <div className="notice-note">
          <Icon name="check" size={15} /> {notice}
        </div>
      ) : null}

      {tab === "users" ? (
        <>
          <div className="toolbar">
            <div className="toolbar-left">
              <span className="muted small">
                {users.filter((item) => item.active).length} active of {users.length} users
              </span>
            </div>
            <Button icon="plus" onClick={() => setUserModal(true)}>
              New user
            </Button>
          </div>
          <Card padded={false}>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th className="align-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <div className="cell-title">{item.email}</div>
                        {item.id === currentUser.id ? (
                          <div className="cell-sub">You</div>
                        ) : null}
                      </td>
                      <td>
                        <select
                          className="select select-sm"
                          value={item.role}
                          disabled={item.id === currentUser.id}
                          onChange={(event) => patchUser(item, { role: event.target.value })}
                        >
                          <option value="admin">Admin</option>
                          <option value="editor">Editor</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      </td>
                      <td>
                        <Badge tone={item.active ? "success" : "neutral"}>
                          {item.active ? "Active" : "Inactive"}
                        </Badge>
                      </td>
                      <td className="muted">{formatDate(item.created_at)}</td>
                      <td className="align-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={item.id === currentUser.id}
                          onClick={() => patchUser(item, { active: !item.active })}
                        >
                          {item.active ? "Deactivate" : "Activate"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      ) : (
        <>
          <div className="toolbar">
            <div className="toolbar-left">
              <span className="muted small">
                Machine credentials for PDM and ERP connectors.
              </span>
            </div>
            <Button icon="plus" onClick={() => setKeyModal(true)}>
              Create API key
            </Button>
          </div>

          {keys.length === 0 ? (
            <Card>
              <EmptyState
                icon="key"
                title="No API keys"
                description="Create a key for the SolidWorks PDM connector or your ERP adapter."
                action={
                  <Button icon="plus" onClick={() => setKeyModal(true)}>
                    Create the first key
                  </Button>
                }
              />
            </Card>
          ) : (
            <Card padded={false}>
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Prefix</th>
                      <th>Last used</th>
                      <th>Created</th>
                      <th>Status</th>
                      <th className="align-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {keys.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div className="cell-title">{item.name}</div>
                        </td>
                        <td className="mono">{item.prefix}…</td>
                        <td className="muted">
                          {item.last_used_at ? timeAgo(item.last_used_at) : "Never"}
                        </td>
                        <td className="muted">{formatDate(item.created_at)}</td>
                        <td>
                          <Badge tone={item.revoked_at ? "danger" : "success"}>
                            {item.revoked_at ? "Revoked" : "Active"}
                          </Badge>
                        </td>
                        <td className="align-right">
                          {!item.revoked_at ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              icon="trash"
                              onClick={() => setToRevoke(item)}
                            >
                              Revoke
                            </Button>
                          ) : (
                            <span className="muted small">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}
        </>
      )}

      <Modal
        open={userModal}
        title="Create user"
        onClose={() => setUserModal(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setUserModal(false)}>
              Cancel
            </Button>
            <Button
              onClick={createUser}
              loading={savingUser}
              disabled={!newEmail.trim() || newPassword.length < 8}
            >
              Create user
            </Button>
          </>
        }
      >
        <div className="stack">
          {error ? <ErrorNote message={error} /> : null}
          <Field label="Email">
            <input
              className="input"
              type="email"
              value={newEmail}
              onChange={(event) => setNewEmail(event.target.value)}
              placeholder="name@company.com"
            />
          </Field>
          <Field label="Temporary password" hint="At least 8 characters.">
            <input
              className="input"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
          </Field>
          <Field label="Role">
            <select
              className="select"
              value={newRole}
              onChange={(event) => setNewRole(event.target.value)}
            >
              <option value="viewer">Viewer — generate and search</option>
              <option value="editor">Editor — manage rules and codes</option>
              <option value="admin">Admin — full control</option>
            </select>
          </Field>
        </div>
      </Modal>

      <Modal
        open={keyModal}
        title={createdKey ? "API key created" : "Create API key"}
        onClose={() => {
          setKeyModal(false);
          setCreatedKey(null);
        }}
        footer={
          createdKey ? (
            <Button onClick={() => { setKeyModal(false); setCreatedKey(null); }}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={() => setKeyModal(false)}>
                Cancel
              </Button>
              <Button
                onClick={createKey}
                loading={creatingKey}
                disabled={keyName.trim().length < 2}
              >
                Create key
              </Button>
            </>
          )
        }
      >
        {createdKey ? (
          <div className="stack">
            <div className="warning-note">
              Copy this secret now. It will not be shown again.
            </div>
            <div className="secret-box">
              <code>{createdKey.key}</code>
            </div>
            <CopyButton value={createdKey.key} label="Copy secret" />
            <p className="muted small">
              Send it to the PDM connector as the <code>X-API-Key</code> header.
            </p>
          </div>
        ) : (
          <div className="stack">
            {error ? <ErrorNote message={error} /> : null}
            <Field label="Key name" hint="For example: SolidWorks PDM production.">
              <input
                className="input"
                value={keyName}
                onChange={(event) => setKeyName(event.target.value)}
                placeholder="PDM connector"
              />
            </Field>
            <div className="info-banner">
              <Icon name="shield" size={16} />
              The key inherits this tenant's rules and can reserve codes. Store it in
              the connector's secret manager, never in source control.
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(toRevoke)}
        title="Revoke API key"
        onClose={() => setToRevoke(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setToRevoke(null)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={revokeKey} loading={revoking}>
              Revoke key
            </Button>
          </>
        }
      >
        <p>
          <strong>{toRevoke?.name}</strong> ({toRevoke?.prefix}…) will stop working
          immediately. Connectors using it will receive 401 responses.
        </p>
      </Modal>

      <p className="muted small">
        Signed in as {currentUser.email} · {titleCase(currentUser.role)}
      </p>
    </div>
  );
}
