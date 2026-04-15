from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
import threading
from typing import TYPE_CHECKING

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse

from . import compose, git, github
from . import state as project_state
from .config import Config
from .discovery import InvalidProject, discover, load_project

if TYPE_CHECKING:
    from .daemon import Daemon

log = logging.getLogger(__name__)

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
_ACTIONS_PROJECT = {"start", "stop", "restart", "protect", "unprotect"}
_ACTIONS_SERVICE = {"start", "stop", "restart"}


def _check_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid name")
    return name


def _require_token(request: Request) -> None:
    expected = os.environ.get("GIVERNY_API_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=500, detail="api token not configured")
    got = request.headers.get("X-Giverny-Token", "")
    if not hmac.compare_digest(expected, got):
        raise HTTPException(status_code=401, detail="unauthorized")


def _docker_ps(project: str) -> list[dict]:
    result = subprocess.run(
        ["docker", "compose", "-p", project, "ps", "--all", "--format", "json"],
        capture_output=True, text=True, check=False,
    )
    out = []
    for line in (result.stdout or "").strip().splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append({
            "name": obj.get("Service") or obj.get("Name", "?"),
            "state": obj.get("State", "?"),
            "health": obj.get("Health") or None,
        })
    return out


def build_app(config: Config, daemon: "Daemon | None" = None) -> FastAPI:
    app = FastAPI(title="giverny")

    def _project(name: str):
        _check_name(name)
        try:
            return load_project(config.services_dir / name, config.default_idle_timeout_minutes)
        except (FileNotFoundError, InvalidProject) as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    @app.get("/api/projects", dependencies=[Depends(_require_token)])
    def list_projects():
        out = []
        for p in discover(config.services_dir, config.default_idle_timeout_minutes):
            services = _docker_ps(p.name)
            suspended = not any(
                s.get("name") == "web" and s.get("state") == "running"
                for s in services
            )
            out.append({
                "name": p.name,
                "hostname": f"{config.root_domain}/{p.name}",
                "web_port": p.web_port,
                "protected": p.protected,
                "idle_timeout_minutes": p.idle_timeout_minutes,
                "suspended": suspended,
                "link": p.link,
                "services": services,
                "build": daemon.build_status(p.name) if daemon else None,
            })
        return out

    @app.get("/api/projects/{name}/build-log", dependencies=[Depends(_require_token)])
    def build_log(name: str):
        _check_name(name)
        if daemon is None:
            raise HTTPException(status_code=500, detail="daemon not wired")
        return {"lines": daemon.build_log(name)}

    @app.get("/api/projects/{name}/services/{service}/log",
             dependencies=[Depends(_require_token)])
    def service_log(name: str, service: str, tail: int = 500):
        _check_name(service)
        p = _project(name)
        tail = max(1, min(2000, int(tail)))
        result = subprocess.run(
            ["docker", "compose", "-p", p.name, "-f", str(p.compose_file),
             "logs", "--no-color", f"--tail={tail}", service],
            capture_output=True, text=True, check=False,
        )
        lines = (result.stdout or "").splitlines()
        if result.returncode != 0 and result.stderr:
            lines.append(f"[stderr] {result.stderr.strip()}")
        return {"lines": lines}

    @app.post("/api/projects/{name}/rebuild", dependencies=[Depends(_require_token)])
    def rebuild(name: str):
        p = _project(name)
        if not p.link:
            raise HTTPException(status_code=400, detail="project is not linked")
        if daemon is None:
            raise HTTPException(status_code=500, detail="daemon not wired")
        started = daemon.rebuild(name)
        if not started:
            raise HTTPException(status_code=409, detail="build already in progress")
        return {"ok": True}

    @app.post("/api/projects/{name}/idle-timeout", dependencies=[Depends(_require_token)])
    def set_idle_timeout(name: str, payload: dict):
        _check_name(name)
        try:
            minutes = int(payload.get("minutes"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="minutes must be an integer")
        if minutes < 0 or minutes > 1440:
            raise HTTPException(status_code=400, detail="minutes out of range (0..1440)")
        project_dir = config.services_dir / name
        if not project_dir.exists():
            raise HTTPException(status_code=404, detail="project not found")
        project_state.mutate(project_dir, idle_timeout_minutes=minutes)
        return {"ok": True, "minutes": minutes}

    @app.post("/api/projects/{name}/{action}", dependencies=[Depends(_require_token)])
    def project_action(name: str, action: str):
        if action not in _ACTIONS_PROJECT:
            raise HTTPException(status_code=400, detail="invalid action")
        p = _project(name)
        if action == "start":
            compose.up(p.name, p.compose_file)
        elif action == "stop":
            compose.down(p.name, p.compose_file)
        elif action == "restart":
            compose.run(p.name, p.compose_file, "restart")
        else:
            project_state.mutate(config.services_dir / p.name,
                                 protected=(action == "protect"))
        return {"ok": True}

    @app.post("/api/projects/{name}/services/{service}/{action}", dependencies=[Depends(_require_token)])
    def service_action(name: str, service: str, action: str):
        if action not in _ACTIONS_SERVICE:
            raise HTTPException(status_code=400, detail="invalid action")
        _check_name(service)
        p = _project(name)
        compose.run(p.name, p.compose_file, action, service)
        return {"ok": True}

    @app.post("/api/link", dependencies=[Depends(_require_token)])
    async def link(payload: dict):
        name = (payload.get("name") or "").strip()
        repo = (payload.get("repo") or "").strip()
        branch = (payload.get("branch") or "main").strip()
        if not name or not repo:
            raise HTTPException(status_code=400, detail="name and repo required")
        _check_name(name)

        dest = config.services_dir / name
        if dest.exists():
            raise HTTPException(status_code=409, detail=f"{name} already exists")

        try:
            git.clone(repo, branch, dest)
        except subprocess.CalledProcessError as exc:
            raise HTTPException(status_code=400, detail=f"clone failed: {exc.stderr.decode(errors='replace')}")

        webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").strip()
        if not webhook_secret:
            raise HTTPException(status_code=500, detail="GITHUB_WEBHOOK_SECRET not set")
        callback = f"https://{config.root_domain}/__giverny/webhook/{name}"
        try:
            hook_id = github.create_push_hook(repo, callback, webhook_secret)
        except github.GitHubError as exc:
            raise HTTPException(status_code=400, detail=f"webhook create failed: {exc}")

        project_state.mutate(dest, link={
            "repo": repo, "branch": branch, "hook_id": hook_id,
        })
        return {"ok": True, "webhook": callback, "hook_id": hook_id}

    @app.post("/api/projects/{name}/unlink", dependencies=[Depends(_require_token)])
    def unlink(name: str):
        _check_name(name)
        s = project_state.load(config.services_dir / name)
        if s.link and s.link.get("hook_id") is not None:
            try:
                github.delete_hook(s.link["repo"], int(s.link["hook_id"]))
            except github.GitHubError as exc:
                log.warning("webhook delete failed: %s", exc)
        project_state.mutate(config.services_dir / name, link=None)
        return {"ok": True}

    @app.api_route("/__giverny/wake/{full_path:path}", methods=["GET", "POST"])
    def wake(full_path: str):
        name = full_path.split("/", 1)[0].split("?", 1)[0]
        _check_name(name)
        if daemon is None:
            raise HTTPException(status_code=500, detail="daemon not wired")
        # Block on compose.up if needed, then redirect. compose.up is
        # idempotent, so concurrent racers each do redundant work but
        # state stays correct.
        if daemon.is_suspended(name):
            daemon.wake(name)
        return RedirectResponse(url=f"/{full_path}", status_code=302)

    @app.post("/__giverny/webhook/{name}")
    async def webhook(name: str, request: Request):
        _check_name(name)
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode()
        body = await request.body()
        sig_header = request.headers.get("X-Hub-Signature-256", "")
        if not secret or not sig_header.startswith("sha256="):
            raise HTTPException(status_code=401, detail="missing signature or secret")
        expected = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig_header):
            raise HTTPException(status_code=401, detail="bad signature")

        if request.headers.get("X-GitHub-Event") != "push":
            return {"ok": True, "ignored": "non-push event"}

        p = _project(name)
        if not p.link:
            raise HTTPException(status_code=400, detail="project is not linked")

        ref = (await _json(request, body)).get("ref", "")
        if ref != f"refs/heads/{p.link['branch']}":
            return {"ok": True, "ignored": f"ref {ref}"}

        log.info("webhook pull %s", name)
        if daemon is None:
            raise HTTPException(status_code=500, detail="daemon not wired")
        daemon.rebuild(name)
        return {"ok": True, "deployed": name}

    return app


async def _json(request: Request, body: bytes) -> dict:
    try:
        return json.loads(body)
    except Exception:
        return {}


def serve_in_thread(config: Config, daemon: "Daemon | None" = None,
                    host: str = "0.0.0.0", port: int = 8765) -> None:
    server = uvicorn.Server(uvicorn.Config(build_app(config, daemon=daemon),
                                           host=host, port=port, log_level="info"))
    threading.Thread(target=server.run, name="giverny-api", daemon=True).start()
    log.info("api listening on http://%s:%d", host, port)
