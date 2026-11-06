let csrf = "";
let generation = 0;
let identity: string | null = null;
export function setIdentity(value: string) {
  identity = value;
}
let unauthorized: (() => void) | null = null;
export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export class StaleRequestError extends Error {
  constructor() {
    super("Account changed while request was pending");
    this.name = "StaleRequestError";
  }
}
export function setCSRF(value: string) {
  csrf = value;
}
export function credentialGeneration() {
  return generation;
}
export function clearCredentials() {
  csrf = "";
  identity = null;
  generation += 1;
}
export function onUnauthorized(handler: (() => void) | null) {
  unauthorized = handler;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  options: { signal?: AbortSignal } = {},
): Promise<T> {
  const epoch = generation;
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    signal: options.signal,
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (epoch !== generation) throw new StaleRequestError();
  const subject = response.headers.get("X-Ted-User-ID");
  if (identity && subject && subject !== identity) {
    unauthorized?.();
    throw new StaleRequestError();
  }
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    if (epoch !== generation) throw new StaleRequestError();
    const message = Array.isArray(data.detail)
      ? data.detail
          .map(
            (d: { loc: string[]; msg: string }) =>
              `${d.loc.slice(1).join(".")}: ${d.msg}`,
          )
          .join("; ")
      : data.detail;
    if (response.status === 401 && path !== "/auth/login") unauthorized?.();
    throw new ApiError(
      message || `Request failed (${response.status})`,
      response.status,
    );
  }
  const data = await response.json();
  if (epoch !== generation) throw new StaleRequestError();
  return data;
}
export async function all<T>(path: string): Promise<T[]> {
  const items: T[] = [];
  for (let offset = 0; ; offset += 200) {
    const data = await api<{ items: T[]; total: number }>(
      `${path}${path.includes("?") ? "&" : "?"}limit=200&offset=${offset}`,
    );
    items.push(...data.items);
    if (items.length >= data.total) return items;
  }
}
export const uid = () => crypto.randomUUID();
