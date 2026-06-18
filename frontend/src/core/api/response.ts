export async function parseJsonOrThrow<T>(
  response: Response,
  fallbackMessage: string,
): Promise<T> {
  const text = await response.text();
  let data: unknown = null;

  if (text.trim()) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      data = text;
    }
  }

  if (!response.ok) {
    throw new Error(formatErrorData(data, fallbackMessage, response));
  }

  if (typeof data === "string") {
    throw new Error(`${fallbackMessage}: ${data}`);
  }

  return data as T;
}

function formatErrorData(
  data: unknown,
  fallbackMessage: string,
  response: Response,
): string {
  const detail = extractDetail(data);
  if (detail) return detail;

  if (typeof data === "string" && data.trim()) {
    return data.trim();
  }

  return `${fallbackMessage}: ${response.statusText || response.status}`;
}

function extractDetail(data: unknown): string | null {
  if (!data || typeof data !== "object") return null;
  const detail = (data as { detail?: unknown }).detail;
  return formatDetail(detail);
}

function formatDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (typeof detail === "number" || typeof detail === "boolean") {
    return String(detail);
  }
  if (Array.isArray(detail)) {
    const parts = detail.map(formatDetail).filter(Boolean);
    return parts.length > 0 ? parts.join("; ") : null;
  }
  if (detail && typeof detail === "object") {
    const msg = (detail as { msg?: unknown }).msg;
    if (typeof msg === "string") return msg;
    try {
      return JSON.stringify(detail);
    } catch {
      return null;
    }
  }
  return null;
}
