import { listProjects, type Project } from "./lib/api";
import {
  linkRepo,
  projectAction,
  serviceAction,
  setIdleTimeout,
  unlinkRepo,
} from "./actions";

export const dynamic = "force-dynamic";

function StateBadge({ state }: { state: string }) {
  const color =
    state === "running"
      ? "bg-green-500/20 text-green-400"
      : state === "exited" || state === "stopped"
        ? "bg-zinc-500/20 text-zinc-400"
        : "bg-yellow-500/20 text-yellow-400";
  return (
    <span className={`rounded px-2 py-0.5 text-xs ${color}`}>{state}</span>
  );
}

function ActionButton({
  action,
  children,
}: {
  action: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="submit"
      name="action"
      value={action}
      className="rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800"
    >
      {children}
    </button>
  );
}

export default async function Home() {
  let projects: Project[] = [];
  let error: string | null = null;
  try {
    projects = await listProjects();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="mx-auto max-w-4xl p-6 font-mono text-sm text-zinc-100">
      <h1 className="mb-6 text-xl font-semibold">giverny</h1>

      {error && (
        <div className="mb-4 rounded border border-red-800 bg-red-950/40 p-3 text-red-300">
          daemon unreachable: {error}
        </div>
      )}

      <section className="mb-6 rounded border border-zinc-800 bg-zinc-950 p-4">
        <div className="mb-2 text-base font-semibold">Link a GitHub repo</div>
        <p className="mb-3 text-xs text-zinc-500">
          Clones into <code>services/&lt;name&gt;/</code> and starts it. The
          repo must contain a <code>docker-compose.yml</code> with a{" "}
          <code>web</code> service.
        </p>
        <form
          action={linkRepo}
          className="flex flex-wrap items-end gap-2 text-xs"
        >
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500">name</span>
            <input
              required
              name="name"
              placeholder="my-app"
              className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500">repo</span>
            <input
              required
              name="repo"
              placeholder="owner/repo or full https URL"
              className="w-72 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-zinc-500">branch</span>
            <input
              name="branch"
              defaultValue="main"
              className="w-28 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
            />
          </label>
          <button
            type="submit"
            className="rounded border border-zinc-700 bg-zinc-800 px-3 py-1 hover:bg-zinc-700"
          >
            link
          </button>
        </form>
      </section>

      {projects.length === 0 && !error && (
        <p className="text-zinc-500">no projects discovered</p>
      )}

      <ul className="space-y-4">
        {projects.map((p) => (
          <li
            key={p.name}
            className="rounded border border-zinc-800 bg-zinc-950 p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-base font-semibold">
                  {p.name}
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                      p.protected
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-zinc-700/40 text-zinc-400"
                    }`}
                    title={p.protected ? "basic auth required" : "public"}
                  >
                    {p.protected ? "protected" : "public"}
                  </span>
                  {p.suspended && (
                    <span
                      className="rounded bg-purple-500/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-purple-300"
                      title="containers stopped; next request will auto-wake"
                    >
                      suspended
                    </span>
                  )}
                  {p.idle_timeout_minutes === 0 && (
                    <span
                      className="rounded bg-zinc-700/40 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-zinc-400"
                      title="auto-suspend disabled — containers always on"
                    >
                      always-on
                    </span>
                  )}
                  {p.link && (
                    <span className="rounded bg-sky-500/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-sky-300">
                      linked
                    </span>
                  )}
                </div>
                <a
                  href={`https://${p.hostname}`}
                  className="text-xs text-zinc-400 hover:underline"
                  target="_blank"
                  rel="noreferrer"
                >
                  {p.hostname}
                </a>
                {p.link && (
                  <div className="mt-1 text-xs text-zinc-500">
                    {p.link.repo} @ {p.link.branch}
                    {" · "}
                    webhook:{" "}
                    <code className="text-zinc-400">
                      /__giverny/webhook/{p.name}
                    </code>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-4">
                <form
                  action={setIdleTimeout}
                  className="flex items-center gap-1 text-xs"
                  title="suspend after N minutes of no requests (0 = never suspend)"
                >
                  <input type="hidden" name="name" value={p.name} />
                  <span className="text-zinc-500">suspend after</span>
                  <input
                    type="number"
                    name="minutes"
                    min={0}
                    max={1440}
                    defaultValue={p.idle_timeout_minutes}
                    className="w-14 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  />
                  <span className="text-zinc-500">min (0 = off)</span>
                  <button
                    type="submit"
                    className="rounded border border-zinc-700 px-2 py-1 hover:bg-zinc-800"
                  >
                    save
                  </button>
                </form>
                <form action={projectAction}>
                  <input type="hidden" name="name" value={p.name} />
                  <ActionButton action={p.protected ? "unprotect" : "protect"}>
                    {p.protected ? "unprotect" : "protect"}
                  </ActionButton>
                </form>
                {p.link && (
                  <form action={unlinkRepo}>
                    <input type="hidden" name="name" value={p.name} />
                    <button
                      type="submit"
                      className="rounded border border-zinc-700 px-2 py-1 text-xs hover:bg-zinc-800"
                    >
                      unlink
                    </button>
                  </form>
                )}
                <form action={projectAction} className="flex gap-2">
                  <input type="hidden" name="name" value={p.name} />
                  <ActionButton action="start">start</ActionButton>
                  <ActionButton action="restart">restart</ActionButton>
                  <ActionButton action="stop">stop</ActionButton>
                </form>
              </div>
            </div>

            <table className="w-full border-collapse text-xs">
              <thead className="text-zinc-500">
                <tr>
                  <th className="py-1 text-left">service</th>
                  <th className="py-1 text-left">state</th>
                  <th className="py-1 text-right">actions</th>
                </tr>
              </thead>
              <tbody>
                {p.services.length === 0 && (
                  <tr>
                    <td colSpan={3} className="py-1 text-zinc-500">
                      no containers
                    </td>
                  </tr>
                )}
                {p.services.map((s) => (
                  <tr key={s.name} className="border-t border-zinc-900">
                    <td className="py-1">{s.name}</td>
                    <td className="py-1">
                      <StateBadge state={s.state} />
                      {s.health && (
                        <span className="ml-2 text-zinc-500">{s.health}</span>
                      )}
                    </td>
                    <td className="py-1 text-right">
                      <form
                        action={serviceAction}
                        className="inline-flex gap-2"
                      >
                        <input type="hidden" name="name" value={p.name} />
                        <input
                          type="hidden"
                          name="service"
                          value={s.name}
                        />
                        <ActionButton action="start">start</ActionButton>
                        <ActionButton action="restart">restart</ActionButton>
                        <ActionButton action="stop">stop</ActionButton>
                      </form>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </li>
        ))}
      </ul>
    </main>
  );
}
