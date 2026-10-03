"""Proste bryły: pudełko, domek z dachem dwuspadowym, walec / stożek ścięty."""
from __future__ import annotations

from dataclasses import dataclass

from ..mesh import Mesh
from .base import Model, P, cap, circle_ring


@dataclass
class BoxParams:
    width: float = P("Szerokość [mm]", 80, 10, 250)
    depth: float = P("Głębokość [mm]", 50, 10, 250)
    height: float = P("Wysokość [mm]", 40, 10, 250)


def build_box(p: BoxParams) -> Model:
    m = Mesh()
    w, d, h = p.width, p.depth, p.height
    part = m.add_part("Pudełko", color="#e8c170")
    c = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0), (0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]
    for q in ([0, 3, 2, 1], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7], [4, 5, 6, 7]):
        m.add_face([c[i] for i in q], part)
    return Model(f"Pudełko {w:g}×{d:g}×{h:g} mm", m)


@dataclass
class HouseParams:
    width: float = P("Szerokość (ściana szczytowa) [mm]", 60, 10, 200)
    length: float = P("Długość [mm]", 90, 10, 250)
    wall: float = P("Wysokość ścian [mm]", 45, 5, 200)
    roof: float = P("Wysokość dachu [mm]", 30, 2, 150)


def build_house(p: HouseParams) -> Model:
    m = Mesh()
    w, l, h, r = p.width, p.length, p.wall, p.roof
    walls = m.add_part("Ściany", color="#f1e3c6", tab_priority=1)
    roof = m.add_part("Dach", color="#b5533c")
    floor = m.add_part("Podstawa", color="#b8b8b8", tab_priority=-1)
    a, b, c, d = (0, 0, 0), (w, 0, 0), (w, l, 0), (0, l, 0)
    A, B, C, D = (0, 0, h), (w, 0, h), (w, l, h), (0, l, h)
    r0, r1 = (w / 2, 0, h + r), (w / 2, l, h + r)
    m.add_face([a, b, B, r0, A], walls)      # szczyt przedni
    m.add_face([b, c, C, B], walls)
    m.add_face([c, d, D, r1, C], walls)      # szczyt tylny
    m.add_face([d, a, A, D], walls)
    m.add_face([B, C, r1, r0], roof)
    m.add_face([D, A, r0, r1], roof)
    m.add_face([a, d, c, b], floor)
    return Model(f"Domek {w:g}×{l:g} mm", m)


@dataclass
class FrustumParams:
    r_bottom: float = P("Promień dolny [mm]", 30, 2, 120)
    r_top: float = P("Promień górny [mm] (0 = stożek)", 18, 0, 120)
    height: float = P("Wysokość [mm]", 60, 5, 250)
    segments: int = P("Liczba odcinków obwodu", 24, 8, 72)


def build_frustum(p: FrustumParams) -> Model:
    m = Mesh()
    n = int(p.segments)
    side = m.add_part("Pobocznica", color="#8fb8de", smooth=True, tab_priority=1)
    bottom = m.add_part("Denko dolne", color="#6f93b4")
    # pierścienie w płaszczyźnie XY (oś bryły = Z)
    ring = lambda r, z: [(y, zz, z) for (_, y, zz) in circle_ring(0, r, n)]
    A, B = ring(p.r_bottom, 0), ring(p.r_top, p.height)
    m.loft(A, B, side)
    cap(m, A, bottom)
    if p.r_top > 1e-6:
        top = m.add_part("Denko górne", color="#6f93b4")
        cap(m, B, top)
    kind = "Walec" if abs(p.r_bottom - p.r_top) < 1e-9 else ("Stożek" if p.r_top < 1e-6 else "Stożek ścięty")
    return Model(f"{kind} r={p.r_bottom:g}/{p.r_top:g} h={p.height:g} mm", m)
