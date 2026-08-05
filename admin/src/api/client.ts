const BASE = (import.meta.env.VITE_API_BASE ?? "/api").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function buildUrl(path: string, query?: Record<string, string | number | undefined>) {
  const basePath = path.startsWith("http") ? path : `${BASE}${path}`;
  if (!query) return basePath;
  const q = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== "") q.set(k, String(v));
  });
  const s = q.toString();
  return s ? `${basePath}?${s}` : basePath;
}

async function parseResponse<T>(r: Response): Promise<T> {
  const text = await r.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* empty body or non-JSON */
  }
  if (!r.ok) {
    const err = data as { error?: { message?: string; detail?: unknown } } | null;
    const msg = err?.error?.message ?? r.statusText;
    throw new ApiError(r.status, msg, err?.error?.detail);
  }
  return data as T;
}

export async function apiGet<T>(path: string, query?: Record<string, string | number | undefined>) {
  const r = await fetch(buildUrl(path, query), {
    headers: { Accept: "application/json" },
  });
  return parseResponse<T>(r);
}

export async function apiPost<T>(path: string, body: unknown) {
  const r = await fetch(buildUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(r);
}

export async function apiPut<T>(path: string, body: unknown) {
  const r = await fetch(buildUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
  return parseResponse<T>(r);
}

export async function apiDelete(path: string) {
  const r = await fetch(buildUrl(path), { method: "DELETE" });
  if (!r.ok) {
    const text = await r.text();
    let data: unknown = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      /* */
    }
    const err = data as { error?: { message?: string } } | null;
    throw new ApiError(r.status, err?.error?.message ?? r.statusText, err);
  }
}
