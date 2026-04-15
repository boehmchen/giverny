# giverny

Self-hosted multi-project container platform. Drop a project into `services/<name>/`,
and giverny starts it on an isolated Docker network and exposes it at
`<root_domain>/<name>/` via Cloudflare Tunnel + Caddy.

Each project's `web` service must be configured to serve under its own
`/<name>/` prefix (Next.js: `basePath`; nginx: `location /<name>/`).
Caddy does not strip the prefix — it's passed through unchanged so client
asset URLs line up.

## Setup

1. Create a Cloudflare Tunnel in the Cloudflare dashboard and copy the token.
2. In the tunnel's Public Hostnames, route `<root_domain>` → `http://caddy:80`. Cloudflare auto-creates the DNS record.
3. Edit `giverny.toml` and set `root_domain`.
4. `cp .env.example .env` and paste the tunnel token into `CLOUDFLARE_TUNNEL_TOKEN`.
5. `docker compose up -d`

That's it. Compose auto-loads `.env`, creates both networks, builds the daemon
image, and starts `caddy`, `cloudflared`, `giverny-daemon`. The daemon then
discovers every `services/*/docker-compose.yml` and brings them up.

## Adding a project

Create `services/<project>/docker-compose.yml` with a service named `web`:

```yaml
services:
  web:
    build: ./web
    expose: ["80"]

networks:
  default:
    name: giverny_apps
    external: true
```

The `web` service becomes `https://<root_domain>/<project>/`. No `ports:`
entries are allowed — services are never published to the host. Additional
services in the same compose file are reachable only by siblings on the
private `giverny_apps` network.

## Dashboard

The dashboard is itself a giverny service at `services/dashboard/` — a Next.js
app served at `https://<root_domain>/dashboard/`. It calls the daemon over the
internal `giverny_apps` network at `http://giverny-daemon:8765`.

## Linking a GitHub repo (auto-deploy)

In the dashboard there's a **Link a GitHub repo** form. Enter a project
name, repo (`owner/repo` or full HTTPS URL), and branch. Giverny clones
into `services/<name>/`, starts it, and stores the link info.

For private repos, set a GitHub PAT (fine-grained, **Contents: read**) in
`.env` as `GITHUB_TOKEN`. Also set `GITHUB_WEBHOOK_SECRET` to a random
string (`openssl rand -hex 32`).

After linking, add a GitHub webhook on the repo:

- Payload URL: `https://<root_domain>/__giverny/webhook/<name>`
- Content type: `application/json`
- Secret: value of `GITHUB_WEBHOOK_SECRET`
- Events: *Just the push event.*

On every push to the tracked branch, giverny runs
`git fetch && git reset --hard` inside the project and then
`docker compose up -d --build`.

## Protecting a project

To require HTTP basic auth on a project, drop an empty marker file:

```
touch services/<project>/.protected
```

Caddy will wrap that project's route in `basicauth` using the shared
credentials from `.env` (`GIVERNY_BASIC_AUTH_USER` +
`GIVERNY_BASIC_AUTH_HASH`). To set or change the password:

```
./set-password
```

This prompts, hashes, updates `.env`, and reloads caddy. The dashboard
ships with `.protected` set by default.

## Architecture

See [docs/architecture.md](docs/architecture.md) for diagrams of the
networks, request path, reconcile loop, and isolation model.

## Commands

- `docker compose up -d` — start the edge stack (daemon reconciles from there)
- `docker compose logs -f` — tail edge stack logs
- `docker compose down` — stop everything
- `docker compose ps` — list edge containers

## Isolation

- `giverny_apps` is an `internal` bridge network: no host access, no internet.
- Only `cloudflared` and `caddy` sit on `giverny_edge` (with internet egress).
- No project container publishes a host port.
