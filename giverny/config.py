from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    root_dir: Path
    services_dir: Path
    edge_dir: Path
    root_domain: str
    poll_interval_seconds: float
    default_idle_timeout_minutes: int
    caddy_access_log: Path


def load(root_dir: Path | None = None) -> Config:
    root = (root_dir or Path.cwd()).resolve()
    data = tomllib.loads((root / "giverny.toml").read_text())
    return Config(
        root_dir=root,
        services_dir=root / "services",
        edge_dir=root / "edge",
        root_domain=data["root_domain"],
        poll_interval_seconds=float(data.get("poll_interval_seconds", 5)),
        default_idle_timeout_minutes=int(data.get("default_idle_timeout_minutes", 10)),
        caddy_access_log=Path(data.get("caddy_access_log", "/var/log/caddy/access.log")),
    )
