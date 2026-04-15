from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

STATE_FILE = ".giverny.json"


@dataclass
class State:
    protected: bool = False
    idle_timeout_minutes: int | None = None  # None = use config default
    link: dict | None = None  # {"repo": str, "branch": str, "hook_id": int}


def load(project_dir: Path) -> State:
    p = project_dir / STATE_FILE
    if not p.exists():
        return State()
    try:
        data = json.loads(p.read_text())
    except json.JSONDecodeError:
        return State()
    return State(
        protected=bool(data.get("protected", False)),
        idle_timeout_minutes=data.get("idle_timeout_minutes"),
        link=data.get("link") or None,
    )


def save(project_dir: Path, state: State) -> None:
    p = project_dir / STATE_FILE
    project_dir.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(asdict(state), indent=2) + "\n")


def mutate(project_dir: Path, **fields) -> State:
    s = load(project_dir)
    for k, v in fields.items():
        setattr(s, k, v)
    save(project_dir, s)
    return s
