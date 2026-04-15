import { cookies } from "next/headers";
import {
  Check,
  Hammer,
  Link2,
  Link2Off,
  Loader2,
  Lock,
  LockOpen,
  Play,
  RotateCw,
  Square,
  TriangleAlert,
  X,
} from "lucide-react";
import { listProjects, type BuildState, type Project, type Service } from "./lib/api";
import {
  dismissFlash,
  fetchBuildLog,
  fetchServiceLog,
  linkRepo,
  projectAction,
  rebuildProject,
  serviceAction,
  setIdleTimeout,
  unlinkRepo,
} from "./actions";
import { SubmitButton } from "./components/SubmitButton";
import { LogDrawer } from "./components/LogDrawer";

export const dynamic = "force-dynamic";

function StateBadge({ state, health }: { state: string; health: string | null }) {
  const s = state.toLowerCase();
  const stateCls =
    s === "running"
      ? "bg-green-500/20 text-green-400"
      : s === "restarting" || s === "paused"
        ? "bg-amber-500/20 text-amber-300"
        : s === "exited" || s === "stopped" || s === "dead"
          ? "bg-zinc-500/20 text-zinc-400"
          : "bg-yellow-500/20 text-yellow-300";
  const h = (health || "").toLowerCase();
  const healthCls =
    h === "healthy"
      ? "bg-green-500/15 text-green-400"
      : h === "unhealthy"
        ? "bg-red-500/20 text-red-400"
        : h === "starting"
          ? "bg-amber-500/15 text-amber-300"
          : "bg-zinc-700/40 text-zinc-400";
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`rounded px-2 py-0.5 text-xs ${stateCls}`}>{state}</span>
      {health && (
        <span className={`rounded px-1.5 py-0.5 text-[10px] ${healthCls}`}>
          {health}
        </span>
      )}
    </span>
  );
}

function ago(ts: number | null): string {
  if (!ts) return "";
  const s = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

function BuildChip({ build }: { build: BuildState | null }) {
  if (!build) return null;
  if (build.status === "building") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded bg-indigo-500/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-indigo-300"
        title={`started ${ago(build.started_at)}`}
      >
        <Loader2 className="h-3 w-3 animate-spin" /> building
      </span>
    );
  }
  if (build.status === "error") {
    return (
      <span
        className="inline-flex items-center gap-1 rounded bg-red-500/20 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-red-300"
        title={build.error ?? "build failed"}
      >
        <TriangleAlert className="h-3 w-3" /> build failed
      </span>
    );
  }
  return null;
}

async function readFlash(): Promise<{ label: string; msg: string } | null> {
  const c = (await cookies()).get("giverny_flash");
  if (!c) return null;
  try {
    return JSON.parse(c.value);
  } catch {
    return null;
  }
}

export default async function Home() {
  let projects: Project[] = [];
  let error: string | null = null;
  try {
    projects = await listProjects();
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
  }
  const flash = await readFlash();

  return (
    <main className="mx-auto max-w-6xl p-6 font-mono text-sm text-zinc-100">
      <h1 className="mb-6 text-xl font-semibold">giverny</h1>

      {flash && (
        <div className="mb-4 flex items-start justify-between gap-3 rounded border border-red-800 bg-red-950/40 p-3 text-red-300">
          <div>
            <div className="font-semibold">{flash.label} failed</div>
            <div className="mt-1 text-xs whitespace-pre-wrap break-words text-red-200/80">
              {flash.msg}
            </div>
          </div>
          <form action={dismissFlash}>
            <button
              type="submit"
              className="rounded p-1 hover:bg-red-900/40"
              aria-label="dismiss"
              title="dismiss"
            >
              <X className="h-4 w-4" />
            </button>
          </form>
        </div>
      )}

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
              className="w-80 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
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
          <SubmitButton variant="primary" title="link">
            link
          </SubmitButton>
        </form>
      </section>

      {projects.length === 0 && !error && (
        <p className="text-zinc-500">no projects discovered</p>
      )}

      <ul className="space-y-4">
        {projects.map((p) => (
          <ProjectCard key={p.name} project={p} />
        ))}
      </ul>
    </main>
  );
}

function ProjectCard({ project: p }: { project: Project }) {
  return (
    <li className="rounded border border-zinc-800 bg-zinc-950 p-4">
      <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-[1fr_auto] md:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2 text-base font-semibold">
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
            <BuildChip build={p.build} />
            {p.link && (
              <LogDrawer
                label={`build log — ${p.name}`}
                fetchLog={async () => {
                  "use server";
                  return fetchBuildLog(p.name);
                }}
              />
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
              {p.build?.status === "ok" && p.build.finished_at && (
                <> · deployed {ago(p.build.finished_at)}</>
              )}
              {" · "}
              webhook:{" "}
              <code className="text-zinc-400">
                /__giverny/webhook/{p.name}
              </code>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <form
            action={setIdleTimeout}
            className="flex items-center gap-1 text-xs"
            title="suspend after N minutes of no requests (0 = never suspend)"
          >
            <input type="hidden" name="name" value={p.name} />
            <span className="text-zinc-500">idle</span>
            <input
              type="number"
              name="minutes"
              min={0}
              max={1440}
              defaultValue={p.idle_timeout_minutes}
              className="w-14 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
              title="minutes (0 = always on)"
            />
            <SubmitButton title="save idle timeout">
              <Check className="h-4 w-4" />
            </SubmitButton>
          </form>

          <form action={projectAction}>
            <input type="hidden" name="name" value={p.name} />
            <SubmitButton
              name="action"
              value={p.protected ? "unprotect" : "protect"}
              title={p.protected ? "unprotect" : "protect"}
            >
              {p.protected ? (
                <LockOpen className="h-4 w-4" />
              ) : (
                <Lock className="h-4 w-4" />
              )}
            </SubmitButton>
          </form>

          {p.link && (
            <>
              <form action={rebuildProject}>
                <input type="hidden" name="name" value={p.name} />
                <SubmitButton title="rebuild from linked repo">
                  <Hammer className="h-4 w-4" />
                </SubmitButton>
              </form>
              <form action={unlinkRepo}>
                <input type="hidden" name="name" value={p.name} />
                <SubmitButton title="unlink repo" tone="danger">
                  <Link2Off className="h-4 w-4" />
                </SubmitButton>
              </form>
            </>
          )}

          <form action={projectAction} className="flex gap-1">
            <input type="hidden" name="name" value={p.name} />
            <SubmitButton name="action" value="start" title="start">
              <Play className="h-4 w-4" />
            </SubmitButton>
            <SubmitButton name="action" value="restart" title="restart">
              <RotateCw className="h-4 w-4" />
            </SubmitButton>
            <SubmitButton name="action" value="stop" title="stop" tone="danger">
              <Square className="h-4 w-4" />
            </SubmitButton>
          </form>
        </div>
      </div>

      <div className="rounded border border-zinc-900">
        {p.services.length === 0 ? (
          <div className="px-3 py-2 text-xs text-zinc-500">no containers</div>
        ) : (
          p.services.map((s, i) => (
            <ServiceRow
              key={s.name}
              project={p.name}
              service={s}
              first={i === 0}
            />
          ))
        )}
      </div>

      {!p.link && (
        <div className="mt-2 text-[11px] text-zinc-600">
          <Link2 className="inline h-3 w-3" /> not linked — deploys must be
          manual
        </div>
      )}
    </li>
  );
}

function ServiceRow({
  project,
  service: s,
  first,
}: {
  project: string;
  service: Service;
  first: boolean;
}) {
  return (
    <div
      className={`grid grid-cols-[1fr_auto_auto] items-center gap-3 px-3 py-1.5 text-xs ${
        first ? "" : "border-t border-zinc-900"
      }`}
    >
      <div className="truncate">{s.name}</div>
      <StateBadge state={s.state} health={s.health} />
      <form action={serviceAction} className="flex items-center gap-1">
        <input type="hidden" name="name" value={project} />
        <input type="hidden" name="service" value={s.name} />
        <LogDrawer
          label={`logs — ${project}/${s.name}`}
          fetchLog={async () => {
            "use server";
            return fetchServiceLog(project, s.name);
          }}
        />
        <SubmitButton name="action" value="start" title="start">
          <Play className="h-4 w-4" />
        </SubmitButton>
        <SubmitButton name="action" value="restart" title="restart">
          <RotateCw className="h-4 w-4" />
        </SubmitButton>
        <SubmitButton name="action" value="stop" title="stop" tone="danger">
          <Square className="h-4 w-4" />
        </SubmitButton>
      </form>
    </div>
  );
}
