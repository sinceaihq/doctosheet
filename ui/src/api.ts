// How the UI talks to DocToSheet: the local server (default) or, in the web
// demo, Python running in the browser (see lite.ts). Same requests either way.

export type Backend = (path: string, init: RequestInit) => Promise<Response>;

const token = new URLSearchParams(location.hash.slice(1)).get("token") ?? "";
export const hasToken = token !== "";
// Keep the token out of the visible address and history.
if (token) history.replaceState(null, "", location.pathname);

let backend: Backend = (path, init) =>
  fetch(path, { ...init, headers: { ...(init.headers ?? {}), "X-DocToSheet-Token": token } });

export function setBackend(b: Backend): void {
  backend = b;
}

export const isLite = (): boolean => (globalThis as { DOCTOSHEET_LITE?: boolean }).DOCTOSHEET_LITE === true;

export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await backend(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = ((await res.json()) as { detail?: string }).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res;
}
