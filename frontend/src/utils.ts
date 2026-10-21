export function classNames(
  ...values: Array<string | false | null | undefined>
): string {
  return values.filter(Boolean).join(" ");
}

function parseDate(value: string): Date {
  const hasZone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(value);
  return new Date(hasZone ? value : `${value}Z`);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDateShort(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseDate(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
  });
}

export function timeAgo(value: string | null | undefined): string {
  if (!value) return "—";
  const date = parseDate(value);
  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDateShort(value);
}

export function titleCase(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function humanAction(action: string): string {
  const labels: Record<string, string> = {
    "auth.login": "Signed in",
    "code.generated": "Code generated",
    "rule.created": "Rule created",
    "rule.updated": "Rule updated",
    "rule.archived": "Rule archived",
    "item.updated": "Code updated",
    "item.voided": "Code voided",
    "user.created": "User created",
    "user.updated": "User updated",
    "api_key.created": "API key created",
    "api_key.revoked": "API key revoked",
  };
  return labels[action] ?? titleCase(action.replace(".", " "));
}

export async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}
