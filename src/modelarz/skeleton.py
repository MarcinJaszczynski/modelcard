"""Szkielet: płaskie płyty z tektury wycinane z przekrojów tej samej bryły, pomniejszone
o grubość poszycia, łączone na wpusty (pół na pół)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

from .mesh import Mesh


@dataclass
class Plate:
    label: str
    name: str
    origin: np.ndarray
    u: np.ndarray
    v: np.ndarray
    poly: Polygon
    limit: Polygon          # przekrój bryły — płyta musi się w nim mieścić
    thickness: float = 1.0

    @property
    def normal(self) -> np.ndarray:
        return np.cross(self.u, self.v)

    @property
    def outline(self):
        return self.poly

    def to3d(self, pts2):
        return [self.origin + self.u * x + self.v * y for x, y in pts2]


def largest(geom):
    """Największy wielokąt z geometrii (po odjęciu grubości poszycia mogą zostać okruchy)."""
    if geom.is_empty:
        return Polygon()
    if geom.geom_type == "Polygon":
        return geom
    polys = [g for g in geom.geoms if g.geom_type == "Polygon"]
    return max(polys, key=lambda g: g.area) if polys else Polygon()


def plate_from_slice(mesh: Mesh, label, name, origin, u, v, skin: float, thickness: float,
                     parts=None, clip=None, min_area: float = 4.0) -> Plate | None:
    origin, u, v = (np.asarray(a, float) for a in (origin, u, v))
    sec = mesh.slice(origin, np.cross(u, v), u, v, parts)
    poly = sec.buffer(-skin, join_style="mitre")
    if clip is not None:
        poly = poly.intersection(clip)
    poly = largest(poly)
    if poly.is_empty or poly.area < min_area:
        return None
    return Plate(label, name, origin, u, v, poly, sec, thickness)


def halflap(plates: list[Plate], clearance: float = 0.2) -> int:
    """Wycina wpusty pół na pół w każdej parze prostopadłych, przecinających się płyt."""
    count = 0
    for i, A in enumerate(plates):
        for B in plates[i + 1:]:
            nA, nB = A.normal, B.normal
            d = np.cross(nA, nB)
            if np.linalg.norm(d) < 0.999:
                continue
            d /= np.linalg.norm(d)
            # punkt wspólny obu płaszczyzn
            M = np.array([nA, nB, d])
            p0 = np.linalg.solve(M, np.array([nA @ A.origin, nB @ B.origin, 0.0]))
            ia, ib = _interval(A, p0, d), _interval(B, p0, d)
            if ia is None or ib is None:
                continue
            c0, c1 = max(ia[0], ib[0]), min(ia[1], ib[1])
            if c1 - c0 < 1.0:
                continue
            m = (c0 + c1) / 2
            A.poly = largest(A.poly.difference(_slot(A, p0, d, m, ia[1] + 2, B.thickness + clearance)))
            B.poly = largest(B.poly.difference(_slot(B, p0, d, ib[0] - 2, m, A.thickness + clearance)))
            count += 1
    return count


def _to2(P: Plate, p3):
    q = p3 - P.origin
    return np.array([q @ P.u, q @ P.v])


def _interval(P: Plate, p0, d):
    a, b = _to2(P, p0 - d * 1e4), _to2(P, p0 + d * 1e4)
    hit = LineString([a, b]).intersection(P.poly)
    if hit.is_empty:
        return None
    o, dd = _to2(P, p0), _to2(P, p0 + d) - _to2(P, p0)
    ss = [float((np.array(c) - o) @ dd) for g in getattr(hit, "geoms", [hit]) for c in g.coords]
    return (min(ss), max(ss)) if ss else None


def _slot(P: Plate, p0, d, s0, s1, width):
    a, b = _to2(P, p0 + d * s0), _to2(P, p0 + d * s1)
    return LineString([a, b]).buffer(width / 2, cap_style="flat")


def clip_x(x0, x1):
    return box(x0, -1e5, x1, 1e5)


__all__ = ["Plate", "plate_from_slice", "halflap", "largest", "clip_x", "unary_union"]
