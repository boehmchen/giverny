from __future__ import annotations

import json
import os
import urllib.error
import urllib.request


def _host() -> str:
    # DOCKER_HOST may be tcp://host:port — strip scheme.
    h = os.environ.get("DOCKER_HOST", "tcp://docker-proxy:2375")
    return h.split("://", 1)[-1] if "://" in h else h


def container_rx_bytes(container: str, timeout: float = 5.0) -> int | None:
    """Return cumulative received bytes across all networks for a container,
    or None if the container isn't running (or the API call fails)."""
    url = f"http://{_host()}/containers/{container}/stats?stream=false"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    nets = data.get("networks") or {}
    if not nets:
        return None
    return sum(int(n.get("rx_bytes", 0)) for n in nets.values())


def container_is_running(container: str, timeout: float = 5.0) -> bool:
    url = f"http://{_host()}/containers/{container}/json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return False
    return bool((data.get("State") or {}).get("Running"))
