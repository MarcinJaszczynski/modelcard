"""Układanie części na arkuszach. Wyłącznie obroty i przesunięcia — nigdy skalowanie."""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np
from shapely import affinity

PAGES = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}
MARGIN = 10.0
HEADER = 8.0
FOOTER = 17.0
GAP = 3.0


@dataclass
class Placement:
    page: int
    angle: float   # stopnie
    tx: float
    ty: float

    def apply(self, pts):
        a = math.radians(self.angle)
        c, s = math.cos(a), math.sin(a)
        p = np.asarray(pts, float)
        return p @ np.array([[c, s], [-s, c]]) + np.array([self.tx, self.ty])

    def geom(self, g):
        return affinity.translate(affinity.rotate(g, self.angle, origin=(0, 0)), self.tx, self.ty)


def mrr(g):
    """Najmniejszy prostokąt opisany (shapely ostrzega przy kształtach zdegenerowanych)."""
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return g.minimum_rotated_rectangle


class PackError(Exception):
    pass


def printable(page: str):
    """Prostokąt na części: (x0, y0, x1, y1) w mm, początek układu w lewym dolnym rogu."""
    w, h = PAGES[page]
    return MARGIN, MARGIN + FOOTER, w - MARGIN, h - MARGIN - HEADER


def pack(outlines: list, page: str, labels: list[str] | None = None) -> tuple[list[Placement], int]:
    x0, y0, x1, y1 = printable(page)
    W, H = x1 - x0, y1 - y0
    order = sorted(range(len(outlines)), key=lambda i: -max(_dims(outlines[i])))
    pages: list[list] = []
    result: list = [None] * len(outlines)
    for i in order:
        g0 = outlines[i]
        rect = mrr(g0)
        base = 0.0
        if rect.geom_type == "Polygon":
            c = list(rect.exterior.coords)
            e = max(((c[k], c[k + 1]) for k in range(4)), key=lambda ab: math.dist(*ab))
            base = -math.degrees(math.atan2(e[1][1] - e[0][1], e[1][0] - e[0][0]))
        best = None
        for pg in range(len(pages) + 1):
            placed = pages[pg] if pg < len(pages) else []
            for rot in (0, 90, 180, 270):
                ang = base + rot
                g = affinity.rotate(g0, ang, origin=(0, 0))
                bx0, by0, bx1, by1 = g.bounds
                w, h = bx1 - bx0, by1 - by0
                if w > W + 1e-9 or h > H + 1e-9:
                    continue
                pos = _find(placed, g, w, h, W, H)
                if pos is None:
                    continue
                cand = (pos[1] + h, pos[0], pg, ang, x0 + pos[0] - bx0, y0 + pos[1] - by0)
                if best is None or cand < best:
                    best = cand
            if best is not None:
                break
        if best is None:
            name = labels[i] if labels else str(i)
            w, h = _dims(g0)
            raise PackError(f"część {name} ({w:.0f}×{h:.0f} mm) nie mieści się na arkuszu {page} "
                            f"(pole {W:.0f}×{H:.0f} mm) — wybierz większy arkusz lub mniejszą skalę")
        _, _, pg, ang, tx, ty = best
        pl = Placement(pg, ang, tx, ty)
        if pg == len(pages):
            pages.append([])
        gp = affinity.translate(pl.geom(g0), -x0, -y0)
        pages[pg].append((gp, gp.bounds))
        result[i] = pl
    return result, len(pages)


def _dims(g):
    r = mrr(g)
    if r.geom_type != "Polygon":
        b = g.bounds
        return b[2] - b[0], b[3] - b[1]
    c = list(r.exterior.coords)
    return math.dist(c[0], c[1]), math.dist(c[1], c[2])


def _find(placed, g, w, h, W, H):
    bx0, by0 = g.bounds[:2]
    xs = sorted({0.0} | {b[2] + GAP for _, b in placed})
    ys = sorted({0.0} | {b[3] + GAP for _, b in placed})
    for y in ys:
        if y + h > H + 1e-9:
            break
        for x in xs:
            if x + w > W + 1e-9:
                break
            near = [q for q, b in placed
                    if not (x - GAP >= b[2] or x + w + GAP <= b[0] or y - GAP >= b[3] or y + h + GAP <= b[1])]
            if near:
                moved = affinity.translate(g, x - bx0, y - by0)
                if any(moved.distance(q) < GAP - 1e-6 for q in near):
                    continue
            return x, y
    return None
