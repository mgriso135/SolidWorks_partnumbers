import type {
  ApiKey,
  ApiKeyCreated,
  AuditPage,
  AuthResponse,
  DashboardStats,
  GenerateRequest,
  GenerateResult,
  Item,
  ItemPage,
  ItemUpdate,
  LookupResult,
  Rule,
  RuleInput,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api";
const TOKEN_KEY = "partcode.token";

let token: string | null = localStorage.getItem(TOKEN_KEY);
let unauthorizedHandler: (() => void) | null = null;

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, string>;

  constructor(
    message: string,
    status: number,
    code = "ERROR",
    fields: Record<string, string> = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

export function setToken(value: string | null) {
  token = value;
  if (value) localStorage.setItem(TOKEN_KEY, value);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getToken(): string | null {
  return token;
}

export function onUnauthorized(handler: () => void) {
  unauthorizedHandler = handler;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("Cannot reach the PartCode API", 0, "NETWORK_ERROR");
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && token) {
      setToken(null);
      unauthorizedHandler?.();
    }
    const detail = data?.detail;
    let message = `Request failed (${response.status})`;
    let code = "ERROR";
    let fields: Record<string, string> = {};
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      message = detail.message ?? message;
      code = detail.code ?? code;
      fields = detail.fields ?? {};
    } else if (Array.isArray(detail)) {
      message = detail.map((entry) => entry.msg ?? "Invalid value").join("; ");
      code = "VALIDATION_ERROR";
    }
    throw new ApiError(message, response.status, code, fields);
  }
  return data as T;
}

function json(body: unknown): RequestInit {
  return { method: "POST", body: JSON.stringify(body) };
}

export const api = {
  login: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", json({ email, password })),
  me: () => request<User>("/auth/me"),

  listRules: (params?: { status?: string; document_type?: string }) => {
    const query = new URLSearchParams();
    if (params?.status) query.set("status_filter", params.status);
    if (params?.document_type) query.set("document_type", params.document_type);
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return request<Rule[]>(`/rules${suffix}`);
  },
  getRule: (id: string) => request<Rule>(`/rules/${id}`),
  ruleVersions: (id: string) => request<Rule[]>(`/rules/${id}/versions`),
  createRule: (payload: RuleInput) => request<Rule>("/rules", json(payload)),
  updateRule: (id: string, payload: RuleInput) =>
    request<Rule>(`/rules/${id}`, { method: "PUT", body: JSON.stringify(payload) }),
  archiveRule: (id: string) =>
    request<Rule>(`/rules/${id}/archive`, { method: "POST" }),

  preview: (payload: GenerateRequest) =>
    request<GenerateResult>("/generate/preview", json(payload)),
  generate: (payload: GenerateRequest) =>
    request<GenerateResult>("/generate", json(payload)),

  listItems: (params: {
    q?: string;
    rule_key?: string;
    status_filter?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<ItemPage>(`/items?${query.toString()}`);
  },
  getItem: (id: string) => request<Item>(`/items/${id}`),
  lookupItem: (code: string) =>
    request<Item>(`/items/lookup?code=${encodeURIComponent(code)}`),
  updateItem: (id: string, payload: ItemUpdate) =>
    request<Item>(`/items/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  voidItem: (id: string) => request<Item>(`/items/${id}/void`, { method: "POST" }),

  stats: () => request<DashboardStats>("/admin/stats"),
  audit: (params: {
    action?: string;
    actor_id?: string;
    entity_type?: string;
    limit?: number;
    offset?: number;
  }) => {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== "") query.set(key, String(value));
    });
    return request<AuditPage>(`/admin/audit?${query.toString()}`);
  },

  listUsers: () => request<User[]>("/admin/users"),
  createUser: (payload: { email: string; password: string; role: string }) =>
    request<User>("/admin/users", json(payload)),
  updateUser: (id: string, payload: { role?: string; active?: boolean }) =>
    request<User>(`/admin/users/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  listApiKeys: () => request<ApiKey[]>("/admin/api-keys"),
  createApiKey: (name: string) =>
    request<ApiKeyCreated>("/admin/api-keys", json({ name })),
  revokeApiKey: (id: string) =>
    request<ApiKey>(`/admin/api-keys/${id}`, { method: "DELETE" }),

  lookupPdm: (code: string, key: string) =>
    request<LookupResult>(`/integrations/pdm/lookup?code=${encodeURIComponent(code)}`, {
      headers: { "X-API-Key": key },
    }),
};
