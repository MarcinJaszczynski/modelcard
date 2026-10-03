from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..mesh import Mesh
from ..skeleton import Plate


@dataclass
class Mark:
    pts: list
    closed: bool
    style: str          # 'glue' — miejsce przyklejenia, 'cut' — otwór do wycięcia
    label: str = ""
    normal: tuple | None = None
    seam_of: int | None = None   # część wirtualna, której numer szwu ma dostać etykieta


@dataclass
class Model:
    title: str
    mesh: Mesh
    plates: list[Plate] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    paper: float = 0.25
    card: float = 1.0


def P(label, default, lo=None, hi=None):
    """Pole parametru modelu z opisem dla formularza."""
    return field(default=default, metadata={"label": label, "min": lo, "max": hi})


def circle_ring(x, r, n=24, cz=0.0):
    return [(x, r * math.sin(2 * math.pi * k / n), cz - r * math.cos(2 * math.pi * k / n)) for k in range(n)]


def cap(mesh: Mesh, ring, part: int, color=None):
    return mesh.add_face([np.asarray(p, float) for p in ring], part, color)
