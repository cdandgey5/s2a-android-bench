"""POSIX platform (macOS/Linux). Not implemented in v1 (specs/platform-layer.md, "POSIX implementation")."""
from __future__ import annotations


class PosixPlatform:
    id = "posix"

    def __init__(self) -> None:
        raise NotImplementedError("posix.py is a stub: v1 supports Windows only (D-024)")
