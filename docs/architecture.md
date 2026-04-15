# giverny — architecture

## Components and networks

```mermaid
flowchart LR
    user([User browser])
    cf[Cloudflare edge<br/>TLS terminates here]

    subgraph host["host machine (darwin/linux)"]
        subgraph edge_net["giverny_edge (bridge, internet egress)"]
            cloudflared["cloudflared<br/>tunnel token"]
            caddy["caddy<br/>reverse proxy"]
            daemon["giverny-daemon<br/>python + docker cli"]
        end

        subgraph apps_net["giverny_apps (bridge, internal: true)"]
            daemon2["giverny-daemon"]
            caddy2["caddy"]
            dash["dashboard-web-1<br/>Next.js"]
            ex["example-web-1<br/>nginx"]
            extra["...any services/&lt;name&gt;/web"]
        end

        sock[("/var/run/docker.sock")]
        fs[("./services, ./giverny.toml")]
    end

    user -->|https| cf
    cf -->|encrypted tunnel| cloudflared
    cloudflared -->|http| caddy
    caddy -->|http per-host| dash
    caddy -->|http per-host| ex
    caddy -->|http per-host| extra

    daemon -.mounts.-> sock
    daemon -.mounts.-> fs
    daemon -->|127.0.0.1:8765 inside apps| dash

    caddy === caddy2
    daemon === daemon2

    classDef internal fill:#1f2937,stroke:#334155,color:#e5e7eb
    classDef edge fill:#0f172a,stroke:#1e293b,color:#e5e7eb
    class apps_net internal
    class edge_net edge
```

`caddy` and `giverny-daemon` are dual-homed — shown twice just so the diagram is readable. Only they and `cloudflared` ever have internet egress; project containers live on `giverny_apps` (`internal: true`) and cannot reach the host or the public internet.

## Request path for `foo.yourdomain.com`

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant CF as Cloudflare edge
    participant CT as cloudflared (container)
    participant CA as caddy (container)
    participant W as foo-web-1

    U->>CF: HTTPS GET foo.yourdomain.com
    Note over CF: TLS terminated,<br/>cert from wildcard
    CF->>CT: HTTP over persistent tunnel
    CT->>CA: HTTP Host: foo.yourdomain.com → caddy:80
    CA->>CA: match Caddyfile block<br/>for foo.yourdomain.com
    CA->>W: reverse_proxy foo-web-1:PORT
    W-->>CA: response
    CA-->>CT: response
    CT-->>CF: response
    CF-->>U: HTTPS response
```

DNS resolution is free: the wildcard public hostname on the tunnel creates a `*.yourdomain.com` CNAME to the tunnel, so any new subdomain resolves with zero additional config.

## Daemon reconcile loop

```mermaid
flowchart TD
    start([tick every poll_interval_seconds])
    scan["scan services/*/docker-compose.yml"]
    validate{validate: has 'web'?<br/>no host ports?}
    skip["log warning, skip"]
    diff["diff against last tick"]
    startp["docker compose -p &lt;name&gt; up -d<br/>for new/changed"]
    stopp["docker compose -p &lt;name&gt; down<br/>for vanished"]
    render["render edge/Caddyfile"]
    changed{bytes changed?}
    reload["docker exec giverny-caddy<br/>caddy reload"]
    sleep([sleep])

    start --> scan --> validate
    validate -- invalid --> skip --> diff
    validate -- ok --> diff
    diff --> startp --> stopp --> render --> changed
    changed -- yes --> reload --> sleep
    changed -- no --> sleep
    sleep --> start
```

The filesystem is the single source of truth — no state file, no database. Killing and restarting the daemon is a no-op if nothing has changed.

## Adding a new project

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant FS as filesystem
    participant D as giverny-daemon
    participant DE as docker engine
    participant CA as caddy

    You->>FS: mkdir services/foo + write docker-compose.yml
    Note over D: ≤ 5s later<br/>next reconcile tick
    D->>FS: discover services/
    D->>DE: docker compose -p foo up -d
    DE-->>D: foo-web-1 running on giverny_apps
    D->>FS: write edge/Caddyfile<br/>(new http://foo.yourdomain.com block)
    D->>CA: docker exec giverny-caddy caddy reload
    CA-->>D: reloaded
    Note over You,CA: foo.yourdomain.com is now live
```

## Isolation model

```mermaid
flowchart LR
    subgraph edge_only["giverny_edge only"]
        cfl[cloudflared]
    end

    subgraph both["both networks (bridges)"]
        cd[caddy]
        dm[daemon]
    end

    subgraph apps_only["giverny_apps only (internal: true)"]
        svc1[project web]
        svc2[project sidecar]
    end

    inet((public internet))
    host((host 127.0.0.1))

    cfl -->|outbound only| inet
    cd -.->|no host bind| host
    svc1 -. cannot reach .-> inet
    svc1 -. cannot reach .-> host
    svc1 -->|in-network DNS| svc2
    svc1 -->|in-network DNS| dm
    svc1 -->|in-network DNS| cd

    classDef bad stroke:#dc2626,stroke-dasharray: 4 2
    class svc1,svc2 bad
```

- **cloudflared** is the only component that initiates outbound connections — it opens an outbound tunnel; no ports are ever exposed on the host.
- **caddy** and **daemon** bridge `giverny_edge` ↔ `giverny_apps` so reverse proxying and container orchestration work, but they do not publish host ports either.
- **project containers** on `giverny_apps` (`internal: true`) cannot reach the host or the internet. They can only talk to siblings and to caddy/daemon by DNS name inside the network.

## File layout

```mermaid
flowchart TB
    root[giverny/]
    root --> giv[giverny/ - Python package]
    root --> edge[edge/ - managed edge stack]
    root --> svcs[services/ - user projects]
    root --> tl[giverny.toml]

    giv --> daemon[daemon.py]
    giv --> api[api.py - FastAPI]
    giv --> disc[discovery.py]
    giv --> edgepy[edge.py - Caddyfile render]
    giv --> net[network.py]
    giv --> cmp[compose.py - subprocess wrapper]
    giv --> cli[__main__.py - click CLI]

    edge --> edgec[docker-compose.yml]
    edge --> cad[Caddyfile - generated]
    edge --> dfd[daemon/Dockerfile]

    svcs --> dash[dashboard/]
    svcs --> ex[example/]
    svcs --> foo[foo/ - yours]

    dash --> dcomp[docker-compose.yml]
    dash --> web[web/ - Next.js app]
```

## Data flow: dashboard action

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant DB as dashboard-web-1<br/>(Next.js, services/dashboard)
    participant DM as giverny-daemon<br/>(FastAPI :8765)
    participant DE as docker engine (socket)

    U->>DB: click "restart" on project foo
    DB->>DB: Server Action runs in-container
    DB->>DM: POST /api/projects/foo/restart<br/>via giverny_apps DNS
    DM->>DE: docker compose -p foo restart<br/>via /var/run/docker.sock
    DE-->>DM: ok
    DM-->>DB: {ok: true}
    DB->>DB: revalidatePath("/")
    DB-->>U: re-rendered page with fresh state
```

The dashboard never touches the docker socket. It only speaks HTTP to the daemon, which is the single component authorised to orchestrate containers.
