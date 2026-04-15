from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import state as project_state

log = logging.getLogger(__name__)


class InvalidProject(Exception):
    pass


@dataclass(frozen=True)
class Project:
    name: str
    compose_file: Path
    web_port: int
    protected: bool
    idle_timeout_minutes: int
    link: dict | None

    @property
    def web_container(self) -> str:
        return f"{self.name}-web-1"


def load_project(project_dir: Path, default_idle_timeout_minutes: int = 10) -> Project:
    compose_file = next(
        (project_dir / f for f in ("docker-compose.yml", "docker-compose.yaml") if (project_dir / f).exists()),
        None,
    )
    if compose_file is None:
        raise InvalidProject(f"{project_dir.name}: no docker-compose.yml")

    services = (yaml.safe_load(compose_file.read_text()) or {}).get("services") or {}
    if "web" not in services:
        raise InvalidProject(f"{project_dir.name}: no `web` service")
    for name, svc in services.items():
        if svc and svc.get("ports"):
            raise InvalidProject(f"{project_dir.name}: `{name}` uses `ports:`; use `expose:`")
    expose = (services["web"] or {}).get("expose") or []
    if not expose:
        raise InvalidProject(f"{project_dir.name}: `web` must declare `expose: [<port>]`")

    s = project_state.load(project_dir)
    idle = s.idle_timeout_minutes if s.idle_timeout_minutes is not None else default_idle_timeout_minutes
    idle = max(0, min(1440, idle))

    return Project(
        name=project_dir.name,
        compose_file=compose_file,
        web_port=int(str(expose[0]).split("/", 1)[0]),
        protected=s.protected,
        idle_timeout_minutes=idle,
        link=s.link,
    )


def discover(services_dir: Path, default_idle_timeout_minutes: int = 10) -> list[Project]:
    if not services_dir.exists():
        return []
    out: list[Project] = []
    for entry in sorted(services_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith((".", "_")):
            continue
        try:
            out.append(load_project(entry, default_idle_timeout_minutes))
        except InvalidProject as exc:
            log.warning("skipping project: %s", exc)
    return out
