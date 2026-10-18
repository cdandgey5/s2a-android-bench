"""name -> arm factory. Adding an arm = one folder + one line (specs/adapter-interface.md rule 9)."""
from __future__ import annotations

from abb.arms.plain import PlainArm
from abb.arms.speckit import SpecKitArm

ARMS = {
    "plain": lambda: PlainArm("plain"),
    "plain-guided": lambda: PlainArm("plain-guided", guided=True),
    "plain-gate": lambda: PlainArm("plain-gate", gate=True),
    "speckit": lambda: SpecKitArm("speckit"),
    "speckit-sdd": lambda: SpecKitArm("speckit-sdd", path="sdd"),
}


def get_arm(name: str):
    if name not in ARMS:
        raise KeyError(f"unknown arm {name!r}; known: {sorted(ARMS)}")
    return ARMS[name]()
