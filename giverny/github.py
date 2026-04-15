from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


class GitHubError(Exception):
    pass


def _owner_repo(repo: str) -> tuple[str, str]:
    s = repo.strip()
    if s.startswith("git@"):
        _, tail = s.split(":", 1)
        s = tail
    else:
        p = urlparse(s)
        if p.netloc:
            s = p.path.lstrip("/")
    if s.endswith(".git"):
        s = s[:-4]
    m = re.match(r"^([\w.-]+)/([\w.-]+)$", s)
    if not m:
        raise GitHubError(f"cannot parse owner/repo from {repo!r}")
    return m.group(1), m.group(2)


def _request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | None]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise GitHubError("GITHUB_TOKEN not set")
    req = urllib.request.Request(
        f"https://api.github.com{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "giverny",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return resp.status, (json.loads(data) if data else None)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise GitHubError(f"GitHub {method} {path} → {exc.code}: {detail}") from None


def create_push_hook(repo: str, callback_url: str, secret: str) -> int:
    owner, name = _owner_repo(repo)
    _, body = _request("POST", f"/repos/{owner}/{name}/hooks", {
        "name": "web",
        "active": True,
        "events": ["push"],
        "config": {
            "url": callback_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0",
        },
    })
    if not body or "id" not in body:
        raise GitHubError("hook created but no id returned")
    return int(body["id"])


def delete_hook(repo: str, hook_id: int) -> None:
    owner, name = _owner_repo(repo)
    _request("DELETE", f"/repos/{owner}/{name}/hooks/{hook_id}")
