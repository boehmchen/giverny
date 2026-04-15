from __future__ import annotations

import subprocess
from pathlib import Path


def _base(project: str, compose_file: Path) -> list[str]:
    return ["docker", "compose", "-p", project, "-f", str(compose_file)]


def up(project: str, compose_file: Path) -> None:
    subprocess.run([*_base(project, compose_file), "up", "-d"], check=True, capture_output=True)


def down(project: str, compose_file: Path) -> None:
    subprocess.run([*_base(project, compose_file), "down", "--remove-orphans"],
                   check=True, capture_output=True)


def run(project: str, compose_file: Path, action: str, service: str | None = None) -> None:
    cmd = [*_base(project, compose_file), action]
    if service:
        cmd.append(service)
    subprocess.run(cmd, check=False)
