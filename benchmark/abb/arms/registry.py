"""name -> arm factory. Adding an arm = one folder + one line (specs/adapter-interface.md rule 9)."""
from __future__ import annotations

from abb.arms.plain import PlainArm

ARMS = {
    "plain": lambda: PlainArm("plain"),
    "plain-guided": lambda: PlainArm("plain-guided", guided=True),
    "plain-gate": lambda: PlainArm("plain-gate", gate=True),
}


def get_arm(name: str):
    if name not in ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {sorted(ARMS)}")
    return ARMS[name]()
