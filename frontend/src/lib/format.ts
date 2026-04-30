export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong.";
}

export function getInitials(name: string | null | undefined, email: string): string {
  const source = (name?.trim() || email).replace(/[^a-z0-9 ]/gi, " ");
  const pieces = source.split(/\s+/).filter(Boolean).slice(0, 2);
  if (pieces.length === 0) {
    return "NA";
  }
  return pieces.map((piece) => piece[0]?.toUpperCase() ?? "").join("");
}

export function resolveAssetUrl(value: string | null | undefined): string | null {
  if (!value) {
    return null;
  }
  if (value.startsWith("http://") || value.startsWith("https://") || value.startsWith("/")) {
    return value;
  }
  return `/${value}`;
}

export function estimateReadingMinutes(body: string): number {
  const words = body.trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.ceil(words / 180));
}
