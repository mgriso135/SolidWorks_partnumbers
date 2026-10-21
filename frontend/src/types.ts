export type Role = "admin" | "editor" | "viewer";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  role: Role;
  active: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export type SegmentType =
  | "literal"
  | "separator"
  | "list"
  | "text"
  | "date"
  | "counter"
  | "checksum";

interface BaseSegment {
  key?: string | null;
  label?: string | null;
}

export interface LiteralSegment extends BaseSegment {
  type: "literal";
  value: string;
}

export interface SeparatorSegment extends BaseSegment {
  type: "separator";
  value: string;
}

export interface ListOption {
  value: string;
  label?: string | null;
}

export interface ListSegment extends BaseSegment {
  type: "list";
  key: string;
  label?: string | null;
  required: boolean;
  options: ListOption[];
}

export interface TextSegment extends BaseSegment {
  type: "text";
  key: string;
  label?: string | null;
  required: boolean;
  min_length: number;
  max_length: number;
  regex?: string | null;
}

export interface DateSegment extends BaseSegment {
  type: "date";
  format: string;
}

export interface CounterSegment extends BaseSegment {
  type: "counter";
  key: string;
  padding: number;
  start: number;
  step: number;
  scope: "rule" | "per_value";
  scope_keys: string[];
}

export interface ChecksumSegment extends BaseSegment {
  type: "checksum";
  algorithm: "mod97" | "luhn";
}

export type Segment =
  | LiteralSegment
  | SeparatorSegment
  | ListSegment
  | TextSegment
  | DateSegment
  | CounterSegment
  | ChecksumSegment;

export interface RuleDefinition {
  segments: Segment[];
  max_length: number;
  case: "upper" | "preserve";
}

export interface Rule {
  id: string;
  tenant_id: string;
  key: string;
  name: string;
  description: string;
  document_type: string;
  version: number;
  status: "draft" | "active" | "archived";
  definition: RuleDefinition;
  created_by: string | null;
  created_at: string;
}

export interface RuleInput {
  name: string;
  description: string;
  document_type: string;
  key?: string;
  status: "draft" | "active";
  definition: RuleDefinition;
}

export interface GenerateRequest {
  rule_key: string;
  values: Record<string, string>;
  source?: string;
  external_ref?: string | null;
  metadata?: Record<string, unknown>;
  notes?: string | null;
}

export interface SegmentOutput {
  type: string;
  key?: string | null;
  value: string;
}

export interface GenerateResult {
  code: string;
  rule_key: string;
  rule_version: number;
  item_id: string | null;
  status: string;
  segments: SegmentOutput[];
  created_at: string | null;
}

export interface Item {
  id: string;
  tenant_id: string;
  code: string;
  rule_id: string;
  rule_key: string;
  rule_version: number;
  status: "reserved" | "committed" | "void";
  source: string;
  payload: Record<string, unknown>;
  external_ref: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  voided_at: string | null;
}

export interface ItemPage {
  items: Item[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  key: string;
}

export interface AuditEntry {
  id: string;
  actor_id: string | null;
  actor_type: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: Record<string, unknown>;
  ip: string | null;
  created_at: string;
}

export interface AuditPage {
  items: AuditEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardStats {
  active_rules: number;
  items_total: number;
  items_30d: number;
  items_today: number;
  active_users: number;
  by_source: Record<string, number>;
  recent_items: Item[];
  recent_audit: AuditEntry[];
}

export interface LookupResult {
  exists: boolean;
  item: Item | null;
}

export type Page =
  | "dashboard"
  | "generate"
  | "rules"
  | "rule-editor"
  | "items"
  | "audit"
  | "settings";
