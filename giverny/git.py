from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


def _normalize(repo: str) -> str:
    repo = repo.strip()
    if repo.startswith("git@"):
        _, tail = repo.split(":", 1)
        repo = f"https://github.com/{tail}"
    if re.match(r"^[\w.-]+/[\w.-]+$", repo):
        repo = f"https://github.com/{repo}"
    if not repo.endswith(".git"):
        repo += ".git"
    return repo


def _authed(repo_url: str) -> str:
    url = _normalize(repo_url)
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        return url
    p = urlparse(url)
    return f"https://x-access-token:{token}@{p.netloc}{p.path}"


def clone(repo: str, branch: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "clone", "--branch", branch, "--single-branch", _authed(repo), str(dest)],
        check=True, capture_output=True,
    )


def fetch_reset(repo_dir: Path, repo: str, branch: str) -> None:
    subprocess.run(["git", "-C", str(repo_dir), "remote", "set-url", "origin", _authed(repo)],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "fetch", "origin", branch],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo_dir), "reset", "--hard", f"origin/{branch}"],
                   check=True, capture_output=True)
