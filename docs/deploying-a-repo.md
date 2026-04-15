# Making a repo deployable on giverny

When a user links your repo via `/api/link {name, repo, branch}`, giverny clones
it into `services/<name>/`, starts it with `docker compose`, and reverse-proxies
`https://<root-domain>/<name>/*` to your container.

Everything below is enforced by the daemon (`giverny/discovery.py`,
`giverny/edge.py`). If a requirement is missing, the project is skipped with a
warning in the daemon logs.

## Required files

### `docker-compose.yml` at the repo root

- Must define a service named **`web`** (other services are allowed, but `web`
  is what Caddy reverse-proxies to).
- `web` must declare exactly one `expose:` port, e.g. `expose: ["3000"]`.
  Giverny takes the first exposed port.
- **No service may use `ports:`** — projects are on the internal `giverny_apps`
  network and must never bind host ports. Use `expose:` instead.
- Attach the compose project to the shared `giverny_apps` network:

  ```yaml
  networks:
    default:
      name: giverny_apps
      external: true
  ```

Minimal example:

```yaml
services:
  web:
    build: .
    expose: ["3000"]
    restart: unless-stopped

networks:
  default:
    name: giverny_apps
    external: true
```

### Dockerfile (or pre-built image)

Any `build:` context or `image:` reference works. The daemon builds with
`docker compose up -d --build`, so build context is tarred to the Docker
engine — **do not reference host paths via bind mounts**; daemon does not
expose them.

## Runtime conventions

- **Container name**: docker compose produces `<project-name>-web-1`. Caddy
  routes `https://<root-domain>/<name>/*` → `<name>-web-1:<expose-port>`.
- **Base path**: the proxy does **not strip** the `/<name>` prefix. Your app
  must serve under that prefix:
  - Next.js: set `basePath: "/<name>"` in `next.config.ts`.
  - Vite/React: set `base: "/<name>/"`.
  - Plain static: serve assets at `/<name>/...`.
  - Servers under your control: honor the prefix in routing, or strip it
    yourself.
- **Bind mounts to host FS are forbidden**. The daemon only mounts its own
  narrow paths; user compose files must not `- /some/host/path:/...`. Use
  named volumes.
- **Environment variables** referenced as `- FOO` (no value) are inherited
  from the daemon's process env, which in turn comes from the host's `.env`.
  If your app needs a secret, document which env var name to set.

## Auto-deploy on push

When linked, giverny automatically creates a GitHub push webhook pointing at
`https://<root-domain>/__giverny/webhook/<name>`. On push to the linked
branch, the daemon does `git fetch --reset` + `docker compose up -d --build`.
You do **not** need to configure the webhook yourself.

Requirements for this to work:

- The PAT configured in giverny's `.env` (`GITHUB_TOKEN`) must have
  **Contents: Read** and **Webhooks: Read and write** on your repo.
- Your `docker-compose.yml` must remain valid at the HEAD of the linked
  branch; a broken build leaves the previous containers running.

## Auto-suspend

Idle projects are stopped automatically after N minutes of no HTTP requests
(default 10; configurable per-project from the dashboard; 0 disables).
Volumes are preserved. The first request after suspension hangs for 2–5 s
while the containers start back up, then redirects to the original URL
and serves the response. If the project is protected, basic auth runs
first. No app-side changes needed.

## What giverny does NOT provide

- **No host access.** No host ports, no docker socket, no host bind mounts.
- **No public routing outside `/<name>/*`** — the only external hostname is
  `<root-domain>`, and `/`, `/dashboard`, and `/__giverny/*` are reserved.
- **No database** — bring your own (as another service in your compose file).
- **No persistent storage across recreations** unless you declare a named
  volume in your compose file.

## Checklist

- [ ] `docker-compose.yml` at repo root
- [ ] `web` service present, with `expose: [<port>]` and no `ports:`
- [ ] `networks: default: { name: giverny_apps, external: true }`
- [ ] App serves under the `/<project-name>` base path
- [ ] No host bind mounts; named volumes only
- [ ] Readme documents any required env vars that the operator must add to
      the host `.env`
