"""Logging: one stderr handler, UTC ISO timestamps."""
from __future__ import annotations

import logging
import time

_CONFIGURED = False


def get_logger(name: str = "abb") -> logging.Logger:
    global _CONFIGURED
    if not _CONFIGURED:
        h = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S")
        fmt.converter = time.gmtime
        h.setFormatter(fmt)
        root = logging.getLogger("abb")
        root.addHandler(h)
        root.setLevel(logging.INFO)
        _CONFIGURED = True
    return logging.getLogger(name)
