let csrf = "";
export function setCSRF(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": csrf } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Request failed" }));
    const message = Array.isArray(data.detail)
      ? data.detail
          .map(
            (d: { loc: string[]; msg: string }) =>
              `${d.loc.slice(1).join(".")}: ${d.msg}`,
          )
          .join("; ")
      : data.detail;
    throw new Error(message || `Request failed (${response.status})`);
  }
  return response.json();
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
