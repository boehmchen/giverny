from __future__ import annotations

import logging
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

ADMIN_URL = "http://giverny-caddy:2019"


def load(caddyfile_text: str) -> None:
    req = urllib.request.Request(
        f"{ADMIN_URL}/load",
        data=caddyfile_text.encode(),
        headers={"Content-Type": "text/caddyfile"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"caddy /load failed: {exc.code} {body}")
