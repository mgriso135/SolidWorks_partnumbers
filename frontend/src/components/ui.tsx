import {
  type ButtonHTMLAttributes,
  type ReactNode,
  useEffect,
  useState,
} from "react";
import { copyText } from "../utils";
import { Icon, type IconName } from "./Icon";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "subtle";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "sm" | "md";
  loading?: boolean;
  icon?: IconName;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      className={`btn btn-${variant} btn-${size}${className ? ` ${className}` : ""}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <span className="spinner spinner-sm" /> : icon ? <Icon name={icon} size={16} /> : null}
      {children}
    </button>
  );
}

type Tone = "neutral" | "success" | "warning" | "danger" | "brand" | "info";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

export function Card({
  children,
  className,
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return <div className={`card${padded ? " card-padded" : ""}${className ? ` ${className}` : ""}`}>{children}</div>;
}

export function Field({
  label,
  hint,
  error,
  children,
  className,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <label className={`field${className ? ` ${className}` : ""}`}>
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  width = 560,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  width?: number;
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={onClose}>
      <div
        className="modal"
        style={{ maxWidth: width }}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <Icon name="x" />
          </button>
        </div>
        <div className="modal-body">{children}</div>
        {footer ? <div className="modal-foot">{footer}</div> : null}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="loading-block">
      <span className="spinner" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}

export function EmptyState({
  icon = "box",
  title,
  description,
  action,
}: {
  icon?: IconName;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <Icon name={icon} size={22} />
      </div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action}
    </div>
  );
}

export function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      size="sm"
      icon={copied ? "check" : "copy"}
      onClick={async () => {
        const ok = await copyText(value);
        setCopied(ok);
        window.setTimeout(() => setCopied(false), 1600);
      }}
    >
      {copied ? "Copied" : label}
    </Button>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="error-note" role="alert">
      <Icon name="alert" size={16} />
      <span>{message}</span>
    </div>
  );
}
