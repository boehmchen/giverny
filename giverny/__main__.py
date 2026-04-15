from __future__ import annotations

import logging
import os
from pathlib import Path

from .config import load
from .daemon import Daemon

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

root = os.environ.get("GIVERNY_ROOT")
Daemon(load(root_dir=Path(root) if root else None)).run_in_container()
