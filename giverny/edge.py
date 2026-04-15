from __future__ import annotations

import logging

from . import caddy
from .config import Config
from .discovery import Project

log = logging.getLogger(__name__)


def _project_handle(p: Project) -> list[str]:
    lines = [
        f"    @{p.name} path /{p.name} /{p.name}/*",
        f"    handle @{p.name} {{",
    ]
    if p.protected:
        lines += [
            "        basicauth {",
            "            {env.GIVERNY_BASIC_AUTH_USER} {env.GIVERNY_BASIC_AUTH_HASH}",
            "        }",
        ]
    lines += [
        f"        reverse_proxy {p.web_container}:{p.web_port}",
        "    }",
    ]
    return lines


def render_caddyfile(projects: list[Project], root_domain: str) -> str:
    header = [
        "{",
        "    admin 0.0.0.0:2019",
        "}",
    ]
    if not projects:
        return "\n".join(header + [
            f"http://{root_domain} {{",
            "    respond \"giverny: no projects yet\" 503",
            "}",
        ]) + "\n"

    lines = header + [
        f"http://{root_domain} {{",
        "    @root path /",
        "    handle @root {",
        "        respond \"giverny\" 200",
        "    }",
        "    @webhook path /__giverny/webhook/*",
        "    handle @webhook {",
        "        reverse_proxy giverny-daemon:8765",
        "    }",
    ]
    for p in projects:
        lines.extend(_project_handle(p))
    # Any 502 (upstream unreachable or upstream-returned 502) is routed to
    # the daemon's wake endpoint, which starts the project and serves the
    # loading page. basicauth ran in the per-project handler first, so
    # protected projects still gate on login.
    lines += [
        "    handle_errors {",
        "        @down expression {http.error.status_code} == 502",
        "        handle @down {",
        "            rewrite * /__giverny/wake{uri}",
        "            reverse_proxy giverny-daemon:8765",
        "        }",
        "    }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def reconcile(config: Config, projects: list[Project]) -> None:
    content = render_caddyfile(projects, config.root_domain)
    try:
        caddy.load(content)
    except Exception as exc:
        log.warning("caddy reload failed: %s", exc)
