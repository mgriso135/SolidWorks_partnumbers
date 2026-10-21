import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type {
  ChecksumSegment,
  CounterSegment,
  ListSegment,
  Rule,
  RuleInput,
  Segment,
  SegmentType,
  TextSegment,
} from "../types";
import { titleCase } from "../utils";
import { Badge, Button, Card, ErrorNote, Field, Spinner } from "../components/ui";
import { Icon } from "../components/Icon";

const SEGMENT_TYPES: SegmentType[] = [
  "literal",
  "separator",
  "list",
  "text",
  "date",
  "counter",
  "checksum",
];

function defaultSegment(type: SegmentType): Segment {
  switch (type) {
    case "literal":
      return { type, value: "PRT" };
    case "separator":
      return { type, value: "-" };
    case "list":
      return {
        type,
        key: "family",
        label: "Family",
        required: true,
        options: [
          { value: "MEC", label: "Mechanical" },
          { value: "ELE", label: "Electrical" },
        ],
      };
    case "text":
      return {
        type,
        key: "description",
        label: "Description",
        required: true,
        min_length: 0,
        max_length: 32,
        regex: null,
      };
    case "date":
      return { type, format: "%y" };
    case "counter":
      return {
        type,
        key: "seq",
        padding: 4,
        start: 1,
        step: 1,
        scope: "rule",
        scope_keys: [],
      };
    case "checksum":
      return { type, algorithm: "mod97" };
  }
}

function optionsToText(options: ListSegment["options"]): string {
  return options
    .map((option) => (option.label ? `${option.value}|${option.label}` : option.value))
    .join("\n");
}

function textToOptions(value: string): ListSegment["options"] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [code, ...label] = line.split("|");
      const parsedLabel = label.join("|").trim();
      return {
        value: code.trim(),
        label: parsedLabel || null,
      };
    })
    .filter((option) => option.value !== "");
}

function formatTokens(segments: Segment[]): string[] {
  return segments.map((segment) => {
    switch (segment.type) {
      case "literal":
      case "separator":
        return segment.value;
      case "list":
      case "text":
        return `{${segment.key}}`;
      case "date":
        return `{${segment.format}}`;
      case "counter":
        return "#".repeat(segment.padding);
      case "checksum":
        return "[CHK]";
    }
  });
}

export function RuleEditor({
  ruleId,
  onBack,
  onSaved,
}: {
  ruleId: string | null;
  onBack: () => void;
  onSaved: (rule: Rule) => void;
}) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [documentType, setDocumentType] = useState("part");
  const [key, setKey] = useState("");
  const [status, setStatus] = useState<"active" | "draft">("active");
  const [caseMode, setCaseMode] = useState<"upper" | "preserve">("upper");
  const [maxLength, setMaxLength] = useState(32);
  const [segments, setSegments] = useState<Segment[]>([
    defaultSegment("literal"),
    defaultSegment("separator"),
    defaultSegment("counter"),
  ]);
  const [addType, setAddType] = useState<SegmentType>("list");
  const [existing, setExisting] = useState<Rule | null>(null);
  const [versions, setVersions] = useState<Rule[]>([]);
  const [loading, setLoading] = useState(Boolean(ruleId));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ruleId) return;
    let cancelled = false;
    Promise.all([api.getRule(ruleId), api.ruleVersions(ruleId)])
      .then(([rule, history]) => {
        if (cancelled) return;
        setExisting(rule);
        setVersions(history);
        setName(rule.name);
        setDescription(rule.description);
        setDocumentType(rule.document_type);
        setKey(rule.key);
        setStatus(rule.status === "draft" ? "draft" : "active");
        setCaseMode(rule.definition.case);
        setMaxLength(rule.definition.max_length);
        setSegments(rule.definition.segments);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load rule");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ruleId]);

  const tokens = useMemo(() => formatTokens(segments), [segments]);

  const updateSegment = (index: number, patch: Partial<Segment>) => {
    setSegments((current) =>
      current.map((segment, position) =>
        position === index ? ({ ...segment, ...patch } as Segment) : segment,
      ),
    );
  };

  const replaceType = (index: number, type: SegmentType) => {
    setSegments((current) =>
      current.map((segment, position) =>
        position === index ? defaultSegment(type) : segment,
      ),
    );
  };

  const move = (index: number, direction: -1 | 1) => {
    setSegments((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const copy = [...current];
      [copy[index], copy[target]] = [copy[target], copy[index]];
      return copy;
    });
  };

  const remove = (index: number) => {
    setSegments((current) => current.filter((_, position) => position !== index));
  };

  const save = async () => {
    setError("");
    if (name.trim().length < 2) {
      setError("Rule name must be at least 2 characters.");
      return;
    }
    if (segments.length === 0) {
      setError("A rule needs at least one segment.");
      return;
    }
    const payload: RuleInput = {
      name: name.trim(),
      description: description.trim(),
      document_type: documentType.trim() || "part",
      status,
      definition: {
        segments,
        max_length: maxLength,
        case: caseMode,
      },
    };
    if (!ruleId && key.trim()) payload.key = key.trim();

    setSaving(true);
    try {
      const saved = ruleId
        ? await api.updateRule(ruleId, payload)
        : await api.createRule(payload);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to save the rule");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <Spinner label="Loading rule…" />;

  return (
    <div className="stack">
      <div className="editor-topbar">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <Icon name="chevronRight" size={14} className="rotate-180" /> Back to rules
        </Button>
        <div className="editor-topbar-actions">
          {existing ? (
            <span className="muted small">
              Current version v{existing.version}
              {versions.length > 1 ? ` · ${versions.length} versions` : ""}
            </span>
          ) : null}
          <Button variant="secondary" onClick={onBack}>
            Cancel
          </Button>
          <Button onClick={save} loading={saving} icon="check">
            {ruleId ? "Save new version" : "Create rule"}
          </Button>
        </div>
      </div>

      {error ? <ErrorNote message={error} /> : null}

      {existing && existing.status === "active" ? (
        <div className="info-banner">
          <Icon name="shield" size={16} />
          Saving creates <strong>version {existing.version + 1}</strong> and archives
          version {existing.version}. Existing codes keep their original rule version.
        </div>
      ) : null}

      <div className="editor-grid">
        <div className="stack">
          <Card>
            <div className="card-head">
              <div>
                <h3>Rule details</h3>
                <p>Identity and scope of this numbering rule.</p>
              </div>
            </div>
            <div className="form-grid">
              <Field label="Name">
                <input
                  className="input"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. Mechanical part"
                />
              </Field>
              <Field
                label="Rule key"
                hint={
                  ruleId
                    ? "The key is immutable; new versions reuse it."
                    : "Optional. Derived from the name if left empty."
                }
              >
                <input
                  className="input mono"
                  value={key}
                  disabled={Boolean(ruleId)}
                  onChange={(event) => setKey(event.target.value)}
                  placeholder="mechanical-part"
                />
              </Field>
              <Field label="Document type" className="span-2">
                <input
                  className="input"
                  value={documentType}
                  onChange={(event) => setDocumentType(event.target.value)}
                  placeholder="part, drawing, assembly…"
                />
              </Field>
              <Field label="Description" className="span-2">
                <textarea
                  className="textarea"
                  rows={2}
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="What this rule is used for"
                />
              </Field>
              <Field label="Max code length">
                <input
                  className="input"
                  type="number"
                  min={1}
                  max={128}
                  value={maxLength}
                  onChange={(event) => setMaxLength(Number(event.target.value))}
                />
              </Field>
              <Field label="Letter case">
                <select
                  className="select"
                  value={caseMode}
                  onChange={(event) =>
                    setCaseMode(event.target.value as "upper" | "preserve")
                  }
                >
                  <option value="upper">Uppercase</option>
                  <option value="preserve">Preserve input</option>
                </select>
              </Field>
            </div>
          </Card>

          <Card>
            <div className="card-head">
              <div>
                <h3>Segments</h3>
                <p>Ordered pieces of the code, from left to right.</p>
              </div>
              <div className="add-segment">
                <select
                  className="select select-sm"
                  value={addType}
                  onChange={(event) => setAddType(event.target.value as SegmentType)}
                >
                  {SEGMENT_TYPES.map((type) => (
                    <option key={type} value={type}>
                      {titleCase(type)}
                    </option>
                  ))}
                </select>
                <Button
                  variant="secondary"
                  size="sm"
                  icon="plus"
                  onClick={() => setSegments((current) => [...current, defaultSegment(addType)])}
                >
                  Add
                </Button>
              </div>
            </div>

            <div className="segment-list">
              {segments.map((segment, index) => (
                <div className="segment-editor" key={index}>
                  <div className="segment-editor-head">
                    <span className="segment-index">{index + 1}</span>
                    <select
                      className="select select-sm"
                      value={segment.type}
                      onChange={(event) =>
                        replaceType(index, event.target.value as SegmentType)
                      }
                    >
                      {SEGMENT_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {titleCase(type)}
                        </option>
                      ))}
                    </select>
                    <div className="segment-editor-actions">
                      <button
                        className="icon-btn"
                        onClick={() => move(index, -1)}
                        disabled={index === 0}
                        title="Move up"
                      >
                        <Icon name="arrowUp" size={15} />
                      </button>
                      <button
                        className="icon-btn"
                        onClick={() => move(index, 1)}
                        disabled={index === segments.length - 1}
                        title="Move down"
                      >
                        <Icon name="arrowDown" size={15} />
                      </button>
                      <button
                        className="icon-btn danger"
                        onClick={() => remove(index)}
                        title="Remove"
                      >
                        <Icon name="trash" size={15} />
                      </button>
                    </div>
                  </div>
                  <SegmentFields
                    segment={segment}
                    availableKeys={segments
                      .slice(0, index)
                      .filter(
                        (candidate): candidate is ListSegment | TextSegment =>
                          candidate.type === "list" || candidate.type === "text",
                      )
                      .map((candidate) => candidate.key)}
                    onChange={(patch) => updateSegment(index, patch)}
                  />
                </div>
              ))}
              {segments.length === 0 ? (
                <p className="muted">Add at least one segment to build the code.</p>
              ) : null}
            </div>
          </Card>
        </div>

        <div className="editor-side">
          <Card className="sticky-card">
            <div className="card-head">
              <div>
                <h3>Format preview</h3>
                <p>Tokens are replaced at generation time.</p>
              </div>
            </div>
            <div className="format-preview">
              {tokens.length === 0 ? (
                <span className="muted">Empty rule</span>
              ) : (
                tokens.map((token, index) => (
                  <span className="format-token" key={index}>
                    {token}
                  </span>
                ))
              )}
            </div>
            <div className="preview-note">
              Example structure · {segments.length} segment{segments.length === 1 ? "" : "s"}
            </div>

            <div className="divider" />

            <Field label="Publish as">
              <select
                className="select"
                value={status}
                onChange={(event) => setStatus(event.target.value as "active" | "draft")}
              >
                <option value="active">Active — usable immediately</option>
                <option value="draft">Draft — not usable yet</option>
              </select>
            </Field>
            <Button onClick={save} loading={saving} icon="check" className="full-width">
              {ruleId ? "Save new version" : "Create rule"}
            </Button>
            <p className="muted small center">
              Every save is recorded in the audit log.
            </p>
          </Card>

          {versions.length > 1 ? (
            <Card>
              <div className="card-head">
                <div>
                  <h3>Version history</h3>
                  <p>Newest first.</p>
                </div>
              </div>
              <ul className="version-list">
                {versions.map((version) => (
                  <li key={version.id}>
                    <span className="mono">v{version.version}</span>
                    <Badge
                      tone={
                        version.status === "active"
                          ? "success"
                          : version.status === "draft"
                            ? "warning"
                            : "neutral"
                      }
                    >
                      {titleCase(version.status)}
                    </Badge>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SegmentFields({
  segment,
  availableKeys,
  onChange,
}: {
  segment: Segment;
  availableKeys: string[];
  onChange: (patch: Partial<Segment>) => void;
}) {
  if (segment.type === "literal" || segment.type === "separator") {
    return (
      <div className="segment-fields">
        <Field label="Value">
          <input
            className="input mono"
            value={segment.value}
            onChange={(event) => onChange({ value: event.target.value })}
          />
        </Field>
      </div>
    );
  }

  if (segment.type === "list") {
    return (
      <div className="segment-fields">
        <Field label="Key" hint="Used in the API payload.">
          <input
            className="input mono"
            value={segment.key ?? ""}
            onChange={(event) => onChange({ key: event.target.value })}
          />
        </Field>
        <Field label="Label">
          <input
            className="input"
            value={segment.label ?? ""}
            onChange={(event) => onChange({ label: event.target.value })}
          />
        </Field>
        <Field
          label="Options"
          hint="One per line, using CODE|Label."
          className="span-2"
        >
          <textarea
            className="textarea mono"
            rows={4}
            value={optionsToText(segment.options)}
            onChange={(event) =>
              onChange({ options: textToOptions(event.target.value) })
            }
          />
        </Field>
        <label className="check-row span-2">
          <input
            type="checkbox"
            checked={segment.required}
            onChange={(event) => onChange({ required: event.target.checked })}
          />
          Required field
        </label>
      </div>
    );
  }

  if (segment.type === "text") {
    return (
      <div className="segment-fields">
        <Field label="Key">
          <input
            className="input mono"
            value={segment.key ?? ""}
            onChange={(event) => onChange({ key: event.target.value })}
          />
        </Field>
        <Field label="Label">
          <input
            className="input"
            value={segment.label ?? ""}
            onChange={(event) => onChange({ label: event.target.value })}
          />
        </Field>
        <Field label="Min length">
          <input
            className="input"
            type="number"
            min={0}
            max={64}
            value={segment.min_length}
            onChange={(event) => onChange({ min_length: Number(event.target.value) })}
          />
        </Field>
        <Field label="Max length">
          <input
            className="input"
            type="number"
            min={1}
            max={64}
            value={segment.max_length}
            onChange={(event) => onChange({ max_length: Number(event.target.value) })}
          />
        </Field>
        <Field label="Regex (optional)" className="span-2">
          <input
            className="input mono"
            value={segment.regex ?? ""}
            onChange={(event) => onChange({ regex: event.target.value || null })}
            placeholder="^[A-Z0-9]{3}$"
          />
        </Field>
        <label className="check-row span-2">
          <input
            type="checkbox"
            checked={segment.required}
            onChange={(event) => onChange({ required: event.target.checked })}
          />
          Required field
        </label>
      </div>
    );
  }

  if (segment.type === "date") {
    return (
      <div className="segment-fields">
        <Field label="strftime format" hint="Example: %y for 26, %Y%m for 202610.">
          <input
            className="input mono"
            value={segment.format}
            onChange={(event) => onChange({ format: event.target.value })}
          />
        </Field>
      </div>
    );
  }

  if (segment.type === "counter") {
    return (
      <div className="segment-fields">
        <Field label="Key">
          <input
            className="input mono"
            value={segment.key ?? ""}
            onChange={(event) => onChange({ key: event.target.value })}
          />
        </Field>
        <Field label="Padding">
          <input
            className="input"
            type="number"
            min={1}
            max={12}
            value={segment.padding}
            onChange={(event) => onChange({ padding: Number(event.target.value) })}
          />
        </Field>
        <Field label="Start at">
          <input
            className="input"
            type="number"
            min={0}
            value={segment.start}
            onChange={(event) => onChange({ start: Number(event.target.value) })}
          />
        </Field>
        <Field label="Step">
          <input
            className="input"
            type="number"
            min={1}
            max={1000}
            value={segment.step}
            onChange={(event) => onChange({ step: Number(event.target.value) })}
          />
        </Field>
        <Field label="Scope" className="span-2">
          <select
            className="select"
            value={segment.scope}
            onChange={(event) =>
              onChange({ scope: event.target.value as CounterSegment["scope"] })
            }
          >
            <option value="rule">One counter for the whole rule</option>
            <option value="per_value">Separate counter per combination</option>
          </select>
        </Field>
        {segment.scope === "per_value" ? (
          <Field
            label="Counter keyed by"
            hint={
              availableKeys.length === 0
                ? "Add a list or text segment earlier in the rule."
                : "Each combination gets its own progressive number."
            }
            className="span-2"
          >
            <div className="check-pills">
              {availableKeys.map((candidate) => {
                const checked = segment.scope_keys.includes(candidate);
                return (
                  <label key={candidate} className={`check-pill${checked ? " checked" : ""}`}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => {
                        const next = event.target.checked
                          ? [...segment.scope_keys, candidate]
                          : segment.scope_keys.filter((item) => item !== candidate);
                        onChange({ scope_keys: next });
                      }}
                    />
                    {candidate}
                  </label>
                );
              })}
            </div>
          </Field>
        ) : null}
      </div>
    );
  }

  return (
    <div className="segment-fields">
      <Field label="Algorithm">
        <select
          className="select"
          value={(segment as ChecksumSegment).algorithm}
          onChange={(event) =>
            onChange({
              algorithm: event.target.value as ChecksumSegment["algorithm"],
            })
          }
        >
          <option value="mod97">mod97 → 2 digits</option>
          <option value="luhn">Luhn → 1 digit</option>
        </select>
      </Field>
    </div>
  );
}
