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
class FlatPart:
    """Część płaska spoza poszycia (łopata śmigła, goleń, koło) — wycinana, ewentualnie składana na pół."""
    name: str
    poly: object                 # pełny obrys do wycięcia [mm]
    face: object                 # jedna strona — do podglądu 3D
    color: str
    frames: list                 # [(początek, u, v)] — po jednej kopii części na każde położenie
    folds: list = field(default_factory=list)   # [(a, b)]
    fills: list = field(default_factory=list)   # [(wielokąt, kolor)]
    note: str = "wytnij"
    number: int = 0


@dataclass
class Model:
    title: str
    mesh: Mesh
    plates: list[Plate] = field(default_factory=list)
    marks: list[Mark] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flats: list[FlatPart] = field(default_factory=list)
    paint: list = field(default_factory=list)   # warstwy malowania (paint.Layer)
    face_marks: list = field(default_factory=list)   # [(styl, etykieta, id doklejenia, [(ściana, [łamane lokalne])])]
    paper: float = 0.25
    card: float = 1.0
    shading: float = 0.0     # uplastycznienie brył cieniem (0 = brak)
    wires: list = field(default_factory=list)      # [(nazwa, długość mm, średnica mm, punkt 3D, punkt 3D)]
    joiners: list = field(default_factory=list)    # [(nazwa, pierścień cofnięty, pierścień styku)]


def P(label, default, lo=None, hi=None):
    """Pole parametru modelu z opisem dla formularza."""
    return field(default=default, metadata={"label": label, "min": lo, "max": hi})


def circle_ring(x, r, n=24, cz=0.0):
    return [(x, r * math.sin(2 * math.pi * k / n), cz - r * math.cos(2 * math.pi * k / n)) for k in range(n)]


def cap(mesh: Mesh, ring, part: int, color=None):
    return mesh.add_face([np.asarray(p, float) for p in ring], part, color)
