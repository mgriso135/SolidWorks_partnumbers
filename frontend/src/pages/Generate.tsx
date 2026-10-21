import { useEffect, useMemo, useState } from "react";
import { api, ApiError } from "../api";
import type { GenerateResult, Page, Rule, Segment, User } from "../types";
import { titleCase } from "../utils";
import {
  Badge,
  Button,
  Card,
  CopyButton,
  EmptyState,
  ErrorNote,
  Field,
  Spinner,
} from "../components/ui";
import { Icon } from "../components/Icon";

function initialValues(rule: Rule): Record<string, string> {
  const values: Record<string, string> = {};
  for (const segment of rule.definition.segments) {
    if (segment.type === "list") {
      values[segment.key] = segment.options[0]?.value ?? "";
    } else if (segment.type === "text") {
      values[segment.key] = "";
    }
  }
  return values;
}

function inputSegments(rule: Rule): Array<Extract<Segment, { type: "list" | "text" }>> {
  return rule.definition.segments.filter(
    (segment): segment is Extract<Segment, { type: "list" | "text" }> =>
      segment.type === "list" || segment.type === "text",
  );
}

function isReady(rule: Rule, values: Record<string, string>): boolean {
  return inputSegments(rule).every(
    (segment) => !segment.required || (values[segment.key] ?? "").trim() !== "",
  );
}

function parseMetadata(text: string): Record<string, unknown> | null {
  if (!text.trim()) return null;
  const parsed: unknown = JSON.parse(text);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Metadata must be a JSON object.");
  }
  return parsed as Record<string, unknown>;
}

export function Generate({
  user,
  onNavigate,
}: {
  user: User;
  onNavigate: (page: Page) => void;
}) {
  const [rules, setRules] = useState<Rule[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<GenerateResult | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState<GenerateResult | null>(null);
  const [externalRef, setExternalRef] = useState("");
  const [notes, setNotes] = useState("");
  const [metadataText, setMetadataText] = useState("");
  const [linkError, setLinkError] = useState("");

  const selected = useMemo(
    () => rules.find((rule) => rule.key === selectedKey) ?? null,
    [rules, selectedKey],
  );
  const ready = selected ? isReady(selected, values) : false;

  useEffect(() => {
    let cancelled = false;
    api
      .listRules({ status: "active" })
      .then((data) => {
        if (cancelled) return;
        setRules(data);
        if (data.length > 0) setSelectedKey((current) => current || data[0].key);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof ApiError ? err.message : "Unable to load rules");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    setValues(initialValues(selected));
    setPreview(null);
    setPreviewError("");
    setFieldErrors({});
    setSuccess(null);
    setExternalRef("");
    setNotes("");
    setMetadataText("");
    setLinkError("");
  }, [selected]);

  useEffect(() => {
    if (!selected || !ready) {
      setPreview(null);
      return;
    }
    let cancelled = false;
    setPreviewing(true);
    setPreviewError("");
    const timer = window.setTimeout(() => {
      api
        .preview({ rule_key: selected.key, values })
        .then((result) => {
          if (cancelled) return;
          setPreview(result);
          setFieldErrors({});
        })
        .catch((err) => {
          if (cancelled) return;
          setPreview(null);
          if (err instanceof ApiError) {
            setPreviewError(err.message);
            if (err.code === "INVALID_INPUT") setFieldErrors(err.fields);
          } else {
            setPreviewError("Unable to preview this code");
          }
        })
        .finally(() => {
          if (!cancelled) setPreviewing(false);
        });
    }, 220);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [selected, values, ready]);

  const generate = async () => {
    if (!selected) return;
    setGenerating(true);
    setError("");
    setLinkError("");
    let metadata: Record<string, unknown> | null = null;
    try {
      metadata = parseMetadata(metadataText);
    } catch (err) {
      setLinkError(
        err instanceof Error ? `Invalid metadata: ${err.message}` : "Invalid metadata JSON.",
      );
      setGenerating(false);
      return;
    }
    try {
      const result = await api.generate({
        rule_key: selected.key,
        values,
        external_ref: externalRef.trim() || null,
        notes: notes.trim() || null,
        metadata: metadata ?? undefined,
      });
      setSuccess(result);
      setPreview(result);
      setValues(initialValues(selected));
      setExternalRef("");
      setNotes("");
      setMetadataText("");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
        if (err.code === "INVALID_INPUT") setFieldErrors(err.fields);
      } else {
        setError("Unable to generate the code");
      }
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <Spinner label="Loading rules…" />;
  if (rules.length === 0) {
    return (
      <Card>
        <EmptyState
          icon="rules"
          title="No active coding rule"
          description="Ask an administrator to create and activate a rule before generating codes."
          action={
            user.role === "admin" || user.role === "editor" ? (
              <Button onClick={() => onNavigate("rules")}>Go to coding rules</Button>
            ) : undefined
          }
        />
      </Card>
    );
  }

  return (
    <div className="stack-lg">
      {success ? (
        <div className="success-panel">
          <div className="success-icon">
            <Icon name="check" size={22} />
          </div>
          <div className="success-body">
            <div className="eyebrow success-eyebrow">Code reserved</div>
            <div className="success-code">{success.code}</div>
            <div className="success-meta">
              <Badge tone="success">Saved to registry</Badge>
              <span className="muted">
                {success.rule_key} v{success.rule_version}
              </span>
            </div>
            <div className="success-segments">
              {success.segments.map((segment, index) => (
                <span className="segment-chip" key={`${segment.type}-${index}`}>
                  {segment.value}
                </span>
              ))}
            </div>
          </div>
          <div className="success-actions">
            <CopyButton value={success.code} />
            <Button variant="secondary" onClick={() => onNavigate("items")}>
              Open registry
            </Button>
            <Button variant="ghost" icon="refresh" onClick={() => setSuccess(null)}>
              New code
            </Button>
          </div>
        </div>
      ) : null}

      <div className="generate-grid">
        <Card className="generate-form-card">
          <div className="card-head">
            <div>
              <h3>Rule</h3>
              <p>Select the document type you are creating.</p>
            </div>
          </div>
          <div className="rule-picker">
            {rules.map((rule) => (
              <button
                key={rule.id}
                className={`rule-option${rule.key === selectedKey ? " selected" : ""}`}
                onClick={() => setSelectedKey(rule.key)}
              >
                <span className="rule-option-name">{rule.name}</span>
                <span className="rule-option-meta">
                  {titleCase(rule.document_type)} · v{rule.version}
                </span>
              </button>
            ))}
          </div>

          {selected ? (
            <>
              {selected.description ? (
                <p className="rule-description">{selected.description}</p>
              ) : null}
              <div className="format-strip">
                {selected.definition.segments.map((segment, index) => (
                  <span className="format-token" key={`${segment.type}-${index}`}>
                    {segment.type === "literal" || segment.type === "separator"
                      ? segment.value
                      : segment.type === "list"
                        ? `{${segment.key}}`
                        : segment.type === "text"
                          ? `{${segment.key}}`
                          : segment.type === "date"
                            ? "date"
                            : segment.type === "counter"
                              ? "0000"
                              : "checksum"}
                  </span>
                ))}
              </div>

              <div className="form-grid">
                {inputSegments(selected).map((segment) => {
                  const label =
                    segment.label ?? titleCase(segment.key ?? segment.type);
                  if (segment.type === "list") {
                    return (
                      <Field
                        key={segment.key}
                        label={label}
                        error={fieldErrors[segment.key]}
                        hint={`${segment.options.length} options`}
                      >
                        <div className="option-pills">
                          {segment.options.map((option) => (
                            <button
                              type="button"
                              key={option.value}
                              className={`option-pill${
                                values[segment.key] === option.value ? " selected" : ""
                              }`}
                              onClick={() =>
                                setValues((current) => ({
                                  ...current,
                                  [segment.key]: option.value,
                                }))
                              }
                            >
                              <strong>{option.value}</strong>
                              {option.label ? <span>{option.label}</span> : null}
                            </button>
                          ))}
                        </div>
                      </Field>
                    );
                  }
                  return (
                    <Field
                      key={segment.key}
                      label={label}
                      error={fieldErrors[segment.key]}
                      hint={
                        segment.regex
                          ? `Format: ${segment.regex}`
                          : `${segment.min_length}–${segment.max_length} characters`
                      }
                    >
                      <input
                        className="input"
                        value={values[segment.key] ?? ""}
                        maxLength={segment.max_length}
                        placeholder={`Enter ${label.toLowerCase()}`}
                        onChange={(event) =>
                          setValues((current) => ({
                            ...current,
                            [segment.key]: event.target.value,
                          }))
                        }
                      />
                    </Field>
                  );
                })}
              </div>

              <div className="form-section">
                <div className="card-head">
                  <div>
                    <h3>Link and metadata</h3>
                    <p>Optional. Leave the reference empty for a standalone code.</p>
                  </div>
                </div>
                <div className="form-grid">
                  <Field
                    label="External reference"
                    hint="Example: PDM:VaultName:1234 or vault://Projects/Bracket.SLDPRT"
                    className="span-2"
                  >
                    <input
                      className="input mono"
                      value={externalRef}
                      maxLength={512}
                      placeholder="PDM:VaultName:1234"
                      onChange={(event) => setExternalRef(event.target.value)}
                    />
                  </Field>
                  <Field label="Notes" hint="Internal note stored with this code." className="span-2">
                    <textarea
                      className="textarea"
                      value={notes}
                      maxLength={2000}
                      rows={3}
                      placeholder="Optional context for this code"
                      onChange={(event) => setNotes(event.target.value)}
                    />
                  </Field>
                  <Field
                    label="Metadata (JSON)"
                    hint='Optional JSON object, for example {"material": "S355"}.'
                    error={linkError}
                    className="span-2"
                  >
                    <textarea
                      className="textarea mono"
                      value={metadataText}
                      rows={4}
                      placeholder={'{\n  "material": "S355"\n}'}
                      onChange={(event) => setMetadataText(event.target.value)}
                    />
                  </Field>
                </div>
              </div>
            </>
          ) : null}
        </Card>

        <Card className="generate-preview-card">
          <div className="card-head">
            <div>
              <h3>Preview</h3>
              <p>Updates as you fill the form. Nothing is reserved yet.</p>
            </div>
            {previewing ? <span className="spinner spinner-sm" /> : null}
          </div>

          <div className={`code-display${preview ? " has-code" : ""}`}>
            {preview ? (
              <>
                <span className="code-label">Next code</span>
                <span className="code-value">{preview.code}</span>
                <CopyButton value={preview.code} />
              </>
            ) : (
              <div className="code-placeholder">
                <Icon name="keyboard" size={22} />
                <span>
                  {ready
                    ? "Preview will appear here"
                    : "Complete the required fields to preview"}
                </span>
              </div>
            )}
          </div>

          {preview ? (
            <div className="preview-segments">
              {preview.segments.map((segment, index) => (
                <span className="segment-chip" key={`${segment.type}-${index}`}>
                  {segment.value}
                </span>
              ))}
            </div>
          ) : null}

          {previewError ? <ErrorNote message={previewError} /> : null}
          {error ? <ErrorNote message={error} /> : null}

          <div className="preview-actions">
            <Button
              icon="spark"
              onClick={generate}
              loading={generating}
              disabled={!ready}
            >
              Generate &amp; reserve
            </Button>
            <span className="muted small">
              Rule v{selected?.version} · counter increments on generation
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}
