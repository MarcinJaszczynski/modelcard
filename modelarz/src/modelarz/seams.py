"""Szwy i zakładki. Każda krawędź brzegowa rozwinięcia ma partnera (druga strona tej samej
krawędzi bryły). Sąsiadujące krawędzie o wspólnym partnerze tworzą jeden szew z jednym numerem;
zakładki dostaje dokładnie jedna strona szwu."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Polygon

from .mesh import Mesh
from .unfold import Piece

CORNER_DEG = 40.0   # ostrzejszy narożnik rozdziela szew na dwa
MIN_TAB_EDGE = 1.5  # mm — krótsze krawędzie klei się na styk


@dataclass
class Seam:
    number: int
    keys: list = field(default_factory=list)
    sides: list = field(default_factory=list)   # [(indeks rozwinięcia, [pozycje na obrysie po kolei])]
    tab_side: int = 0
    virtual_part: int | None = None
    length: float = 0.0
    tabbed_length: float = 0.0
    problems: int = 0


class _UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        self.p[self.find(a)] = self.find(b)


def _turn(e1, e2) -> float:
    d1, d2 = e1.b - e1.a, e2.b - e2.a
    return math.atan2(d1[0] * d2[1] - d1[1] * d2[0], float(d1 @ d2))


def build_seams(mesh: Mesh, pieces: list[Piece], tab_h: float = 5.0) -> list[Seam]:
    edges = mesh.edges()
    occ: dict = {}
    for pi, pc in enumerate(pieces):
        for pos, be in enumerate(pc.boundary):
            occ.setdefault(be.key, []).append((pi, pos))
    for pi, pc in enumerate(pieces):
        for pos, be in enumerate(pc.boundary):
            lst = occ[be.key]
            if len(lst) == 2:
                be.partner = lst[0] if lst[1] == (pi, pos) else lst[1]
            else:
                other = [f for f, _ in edges[be.key] if f != be.face]
                be.vpart = mesh.faces[other[0]].part if other else None

    corner = math.radians(CORNER_DEG)
    chain, side = _UF(), _UF()
    for pi, pc in enumerate(pieces):
        n = len(pc.boundary)
        for k in range(n):
            k2 = (k + 1) % n
            e, e2 = pc.boundary[k], pc.boundary[k2]
            if abs(_turn(e, e2)) > corner:
                continue
            if e.partner and e2.partner:
                (qi, j), (qi2, j2) = e.partner, e2.partner
                qb = pieces[qi].boundary
                if qi != qi2 or j2 != (j - 1) % len(qb) or (qi, j) == (pi, k2):
                    continue
                if abs(_turn(qb[j2], qb[j])) > corner:
                    continue
                side.union((qi, j), (qi2, j2))
            elif not (e.partner is None and e2.partner is None and e.vpart is not None and e.vpart == e2.vpart):
                continue
            chain.union(e.key, e2.key)
            side.union((pi, k), (pi, k2))

    seams: dict = {}
    for pi, pc in enumerate(pieces):
        for pos, be in enumerate(pc.boundary):
            if be.partner is None and be.vpart is None:
                continue  # krawędź swobodna
            root = chain.find(be.key)
            sm = seams.get(root)
            if sm is None:
                sm = seams[root] = Seam(number=len(seams) + 1, virtual_part=be.vpart)
            be.seam = sm.number
            sroot = side.find((pi, pos))
            for s in sm.sides:
                if s[2] == sroot:
                    s[1].append(pos)
                    break
            else:
                sm.sides.append([pi, [pos], sroot])
            if be.key not in sm.keys:
                sm.keys.append(be.key)
                sm.length += be.length
    out = list(seams.values())
    for sm in out:
        sm.sides = [(pi, _ordered(poss, len(pieces[pi].boundary))) for pi, poss, _ in sm.sides]
        _place_tabs(mesh, pieces, sm, tab_h)
        for pi, poss in sm.sides:
            pc = pieces[pi]
            spot = np.array(pc.spot[0])

            def at(pos):
                e = pc.boundary[pos]
                d = (e.b - e.a) / max(e.length, 1e-9)
                return (e.a + e.b) / 2 + np.array([-d[1], d[0]]) * 2.4
            pt = at(poss[len(poss) // 2])
            if np.linalg.norm(pt - spot) < 7.0:   # numer szwu nie może wejść pod numer części
                pt = max((at(q) for q in poss), key=lambda c: float(np.linalg.norm(c - spot)))
            pc.seam_labels.append((sm.number, pt))
    return out


def _ordered(poss, n):
    s = set(poss)
    start = next((p for p in sorted(s) if (p - 1) % n not in s), min(s))
    out, p = [], start
    while p in s and len(out) < len(s):
        out.append(p)
        p = (p + 1) % n
    return out + sorted(s - set(out))


def _place_tabs(mesh: Mesh, pieces: list[Piece], sm: Seam, tab_h: float) -> None:
    order = list(range(len(sm.sides)))
    if len(order) == 2:
        pr = [mesh.parts[pieces[sm.sides[i][0]].part].tab_priority for i in order]
        if pr[1] > pr[0]:
            order.reverse()
    best = None
    for si in order:
        pi, poss = sm.sides[si]
        tabs, covered, bad = _tabs_for_side(mesh, pieces[pi], poss, tab_h)
        if best is None or bad < best[3]:
            best = (si, tabs, covered, bad)
        if bad == 0:
            break
    si, tabs, covered, bad = best
    pi, poss = sm.sides[si]
    pc = pieces[pi]
    pc.tabs.extend(tabs)
    pc.tab_problems += bad
    sm.tab_side, sm.tabbed_length, sm.problems = si, covered, bad
    for t in tabs:
        for p in t[3]:
            pc.boundary[p].tabbed = True


def _straight(mesh: Mesh, b, g, tol=0.01) -> bool:
    """Czy krawędzie g leżą w 3D na jednej prostej. Tylko wtedy mogą mieć wspólną zakładkę —
    zakładka nie może przechodzić przez załamanie poszycia."""
    pts = [mesh.V[i] for k in g for i in b[k].key]
    a = pts[0]
    far = max(pts, key=lambda q: float(np.linalg.norm(q - a)))
    a = max(pts, key=lambda q: float(np.linalg.norm(q - far)))
    d = far - a
    L = float(np.linalg.norm(d))
    return L > 1e-9 and all(np.linalg.norm(np.cross(q - a, d)) / L < tol for q in pts)


def _tabs_for_side(mesh: Mesh, pc: Piece, poss: list, tab_h: float):
    b, n = pc.boundary, len(pc.boundary)
    groups = [[poss[0]]]
    for p in poss[1:]:
        prev = groups[-1][-1]
        if p == (prev + 1) % n and _straight(mesh, b, groups[-1] + [p]):
            groups[-1].append(p)
        else:
            groups.append([p])
    tabs, covered, bad = [], 0.0, 0
    existing = [t[0] for t in pc.tabs]
    for g in groups:
        p, q = b[g[0]].a, b[g[-1]].b
        L = float(np.linalg.norm(q - p))
        if L < MIN_TAB_EDGE:
            continue
        d = (q - p) / L
        nrm = np.array([d[1], -d[0]])  # obrys biegnie lewoskrętnie, więc na zewnątrz jest w prawo
        amax = math.radians(45.0 if L > 4 * tab_h else 70.0)
        ap = min(amax, (math.pi + _turn(b[(g[0] - 1) % n], b[g[0]])) / 2 - math.radians(3))
        aq = min(amax, (math.pi + _turn(b[g[-1]], b[(g[-1] + 1) % n])) / 2 - math.radians(3))
        ap, aq = max(ap, math.radians(12)), max(aq, math.radians(12))
        cot = 1 / math.tan(ap) + 1 / math.tan(aq)
        h = min(tab_h, 0.7 * L / cot) if cot > 1e-9 else tab_h
        ok = False
        for _ in range(4):
            poly = Polygon([p, q, q - d * h / math.tan(aq) + nrm * h, p + d * h / math.tan(ap) + nrm * h])
            core = poly.buffer(-0.03)
            if poly.is_valid and not core.is_empty and not core.intersects(pc.body) \
                    and not any(core.intersects(t) for t in existing):
                ok = True
                break
            h *= 0.6
        if not ok:
            bad += 1
            continue
        tabs.append((poly, p, q, list(g)))
        existing.append(poly)
        covered += L
    return tabs, covered, bad
