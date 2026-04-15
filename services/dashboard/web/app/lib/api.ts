export const API_URL = process.env.GIVERNY_API_URL ?? "http://giverny-daemon:8765";

function authHeaders(): Record<string, string> {
  const token = process.env.GIVERNY_API_TOKEN ?? "";
  return token ? { "X-Giverny-Token": token } : {};
}

export type Service = {
  name: string;
  state: string;
  health: string | null;
};

export type Link = { repo: string; branch: string };

export type Project = {
  name: string;
  hostname: string;
  web_port: number;
  protected: boolean;
  idle_timeout_minutes: number;
  suspended: boolean;
  link: Link | null;
  services: Service[];
};

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_URL}/api/projects`, {
    cache: "no-store",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(`listProjects ${res.status}`);
  return res.json();
}

export async function post(path: string, body?: unknown): Promise<void> {
  const headers: Record<string, string> = { ...authHeaders() };
  if (body !== undefined) headers["content-type"] = "application/json";
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    cache: "no-store",
    headers,
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${path} ${res.status} ${text}`);
  }
}
