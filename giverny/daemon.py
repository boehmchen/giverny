from __future__ import annotations

import logging
import signal
import subprocess
import threading
import time
from collections import deque
from typing import Deque

from . import api, compose, dockerapi, edge, git
from .config import Config
from .discovery import Project, discover, load_project

BUILD_LOG_MAX_LINES = 2000

log = logging.getLogger(__name__)


class Daemon:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._running = True
        self._known: dict[str, Project] = {}
        # {project: (last_rx_bytes, timestamp_of_last_change)}
        self._net_stats: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()
        # one per project, to serialize compose.up against itself
        self._wake_locks: dict[str, threading.Lock] = {}
        # build tracking — status is "idle"|"building"|"ok"|"error"
        self._build_state: dict[str, dict] = {}
        self._build_logs: dict[str, Deque[str]] = {}
        self._build_locks: dict[str, threading.Lock] = {}

    def stop(self, *_: object) -> None:
        self._running = False

    def is_suspended(self, name: str) -> bool:
        """A project is 'suspended' iff its web container isn't running."""
        p = self._known.get(name)
        if p is None:
            return False
        return not dockerapi.container_is_running(p.web_container)

    def wake(self, name: str) -> None:
        """Start a project's containers. Serialized per-project so parallel
        callers queue behind each other; the second caller sees the
        container already up and compose.up is a no-op."""
        p = self._known.get(name)
        if p is None:
            return
        with self._lock:
            wl = self._wake_locks.setdefault(name, threading.Lock())
        with wl:
            if dockerapi.container_is_running(p.web_container):
                return
            log.info("waking %s", name)
            compose.up(name, p.compose_file)
            with self._lock:
                self._net_stats.pop(name, None)

    def rebuild(self, name: str) -> bool:
        """Kick off an async git pull + docker compose up --build for a linked
        project. Returns False if a build is already running."""
        p = self._known.get(name) or self._load(name)
        if p is None or not p.link:
            return False
        link: dict = p.link
        with self._lock:
            bl = self._build_locks.setdefault(name, threading.Lock())
        if not bl.acquire(blocking=False):
            return False

        logs: Deque[str] = deque(maxlen=BUILD_LOG_MAX_LINES)
        started = time.time()
        with self._lock:
            self._build_logs[name] = logs
            self._build_state[name] = {
                "status": "building",
                "started_at": started,
                "finished_at": None,
                "error": None,
                "duration_s": None,
            }

        def _run() -> None:
            try:
                logs.append(f"$ git fetch origin {link['branch']}")
                git.fetch_reset(self.config.services_dir / name, link["repo"], link["branch"])
                logs.append("$ docker compose up -d --build")
                proc = subprocess.Popen(
                    ["docker", "compose", "-p", name, "-f", str(p.compose_file),
                     "up", "-d", "--build"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                assert proc.stdout is not None
                for line in proc.stdout:
                    logs.append(line.rstrip("\n"))
                rc = proc.wait()
                ok = rc == 0
                err = None if ok else f"docker compose exited {rc}"
            except subprocess.CalledProcessError as exc:
                ok = False
                err = (exc.stderr or b"").decode(errors="replace")[-2000:] or str(exc)
                logs.append(err)
            except Exception as exc:
                ok = False
                err = f"{type(exc).__name__}: {exc}"
                logs.append(err)
            finished = time.time()
            with self._lock:
                self._build_state[name] = {
                    "status": "ok" if ok else "error",
                    "started_at": started,
                    "finished_at": finished,
                    "error": err,
                    "duration_s": finished - started,
                }
            bl.release()

        threading.Thread(target=_run, daemon=True, name=f"build-{name}").start()
        return True

    def build_status(self, name: str) -> dict | None:
        with self._lock:
            s = self._build_state.get(name)
            return dict(s) if s else None

    def build_log(self, name: str) -> list[str]:
        with self._lock:
            logs = self._build_logs.get(name)
            return list(logs) if logs else []

    def _load(self, name: str) -> Project | None:
        try:
            return load_project(self.config.services_dir / name,
                                self.config.default_idle_timeout_minutes)
        except Exception:
            return None

    def tick(self) -> None:
        current = {p.name: p for p in discover(self.config.services_dir,
                                               self.config.default_idle_timeout_minutes)}
        for name, p in current.items():
            prev = self._known.get(name)
            if prev is None or prev.compose_file != p.compose_file:
                log.info("starting %s", name)
                compose.up(name, p.compose_file)
                with self._lock:
                    self._net_stats.pop(name, None)
        for name, prev in self._known.items():
            if name not in current:
                log.info("stopping %s", name)
                compose.down(name, prev.compose_file)
                with self._lock:
                    self._net_stats.pop(name, None)
        self._known = current
        edge.reconcile(self.config, list(current.values()))
        self._idle_check(current)

    def _idle_check(self, current: dict[str, Project]) -> None:
        now = time.time()
        for name, p in current.items():
            if p.idle_timeout_minutes <= 0:
                continue
            rx = dockerapi.container_rx_bytes(p.web_container)
            if rx is None:
                # container not running — nothing to do
                continue
            prev = self._net_stats.get(name)
            if prev is None or rx != prev[0]:
                self._net_stats[name] = (rx, now)
                continue
            if now - prev[1] < p.idle_timeout_minutes * 60:
                continue
            log.info("suspending %s (idle %.0fs)", name, now - prev[1])
            try:
                compose.down(name, p.compose_file)
            except Exception:
                log.exception("suspend %s: compose down failed", name)
            else:
                self._net_stats.pop(name, None)

    def run_in_container(self) -> None:
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
        api.serve_in_thread(self.config, daemon=self)
        log.info("daemon started (poll=%ss, default_idle=%dm)",
                 self.config.poll_interval_seconds,
                 self.config.default_idle_timeout_minutes)
        while self._running:
            try:
                self.tick()
            except Exception:
                log.exception("reconcile tick failed")
            for _ in range(int(self.config.poll_interval_seconds * 10)):
                if not self._running:
                    break
                time.sleep(0.1)
        log.info("daemon stopping")
