from __future__ import annotations

import logging
import signal
import threading
import time

from . import api, compose, dockerapi, edge
from .config import Config
from .discovery import Project, discover

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
