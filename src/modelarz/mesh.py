"""Bryła 3D: siatka płaskich wielokątów pogrupowanych w części. Jednostki: mm.

To jest jedyne źródło prawdy — rozwinięcia, zakładki, szkielet i podgląd
powstają wyłącznie z tej siatki.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

WELD = 1e-5  # mm — punkty bliżej siebie są tym samym wierzchołkiem


@dataclass
class Part:
    name: str
    color: str = "#d9d9d9"
    smooth: bool = False        # powierzchnia zwijana (nie rysujemy tworzących)
    virtual: bool = False       # zamyka bryłę, ale nie jest drukowana (np. nasada skrzydła)
    tab_priority: int = 0       # wyższy = ta część dostaje zakładki na wspólnym szwie
    cuts: set = field(default_factory=set)  # krawędzie, na których rozwinięcie ma być rozcięte
    number: int = 0             # numer części na arkuszu (nadawany w pipeline)
    group: str = ""             # do czego należy (kadłub, skrzydło…) — używane przez malowanie


@dataclass
class Face:
    verts: tuple
    part: int
    color: str | None = None
    shade: str | None = None    # kolor po malowaniu, w środku ściany (podgląd 3D)


def ekey(a: int, b: int) -> tuple:
    return (a, b) if a < b else (b, a)


class Mesh:
    def __init__(self):
        self.V: list[np.ndarray] = []
        self._vi: dict = {}
        self.faces: list[Face] = []
        self.parts: list[Part] = []
        self.attach: dict = {}   # krawędzie otwarte po docięciu -> identyfikator miejsca doklejenia

    # --- budowanie -------------------------------------------------------
    def vertex(self, p) -> int:
        key = tuple(int(round(float(c) / WELD)) for c in p)
        i = self._vi.get(key)
        if i is None:
            i = len(self.V)
            self._vi[key] = i
            self.V.append(np.array(p, dtype=float))
        return i

    def add_part(self, name: str, **kw) -> int:
        self.parts.append(Part(name=name, **kw))
        return len(self.parts) - 1

    def add_face(self, pts, part: int, color: str | None = None):
        idx = []
        for p in pts:
            i = self.vertex(p)
            if not idx or idx[-1] != i:
                idx.append(i)
        while len(idx) > 1 and idx[0] == idx[-1]:
            idx.pop()
        if len(set(idx)) < 3:
            return None
        self.faces.append(Face(tuple(idx), part, color))
        return len(self.faces) - 1

    def loft(self, A, B, part, cut_at: int | None = 0):
        """Pas ścian między dwoma zamkniętymi pierścieniami o tej samej liczbie punktów.
        `part` może być funkcją k -> część, gdy różne odcinki obwodu należą do różnych części."""
        pick = part if callable(part) else (lambda k: part)
        n = len(A)
        assert n == len(B)
        A = [np.asarray(p, float) for p in A]
        B = [np.asarray(p, float) for p in B]
        for k in range(n):
            a0, a1, b0, b1 = A[k], A[(k + 1) % n], B[k], B[(k + 1) % n]
            if _planar([a0, a1, b1, b0]):
                self.add_face([a0, a1, b1, b0], pick(k))
            elif np.linalg.norm(a0 - b1) <= np.linalg.norm(a1 - b0):
                self.add_face([a0, a1, b1], pick(k))
                self.add_face([a0, b1, b0], pick(k))
            else:
                self.add_face([a0, a1, b0], pick(k))
                self.add_face([a1, b1, b0], pick(k))
        if cut_at is not None:
            ia, ib = self.vertex(A[cut_at]), self.vertex(B[cut_at])
            if ia != ib:
                self.parts[pick(cut_at)].cuts.add(ekey(ia, ib))

    # --- topologia -------------------------------------------------------
    def edges(self) -> dict:
        """klucz krawędzi -> [(ściana, indeks krawędzi w ścianie)]"""
        out: dict = {}
        for fi, f in enumerate(self.faces):
            n = len(f.verts)
            for i in range(n):
                out.setdefault(ekey(f.verts[i], f.verts[(i + 1) % n]), []).append((fi, i))
        return out

    def orient(self) -> None:
        """Ujednolica zwroty ścian (normalne na zewnątrz). Wymaga zamkniętych brył."""
        edges = self.edges()
        for key, lst in edges.items():
            if len(lst) == 1 and key in self.attach:
                continue
            if len(lst) != 2:
                names = {self.parts[self.faces[f].part].name for f, _ in lst}
                raise ValueError(f"siatka nie jest zamknięta/rozmaitościowa na krawędzi {key}: {names}")
        seen = [False] * len(self.faces)
        for start in range(len(self.faces)):
            if seen[start]:
                continue
            comp, stack = [start], [start]
            seen[start] = True
            while stack:
                f = stack.pop()
                vs = self.faces[f].verts
                n = len(vs)
                for i in range(n):
                    a, b = vs[i], vs[(i + 1) % n]
                    for g, _ in edges[ekey(a, b)]:
                        if g == f or seen[g]:
                            continue
                        gv = self.faces[g].verts
                        m = len(gv)
                        same_dir = any(gv[j] == a and gv[(j + 1) % m] == b for j in range(m))
                        if same_dir:
                            self.faces[g].verts = tuple(reversed(gv))
                        seen[g] = True
                        comp.append(g)
                        stack.append(g)
            closed = all(len(edges[ekey(vs[i], vs[(i + 1) % len(vs)])]) == 2
                         for f in comp for vs in [self.faces[f].verts] for i in range(len(vs)))
            if closed and self._volume(comp) < 0:
                for f in comp:
                    self.faces[f].verts = tuple(reversed(self.faces[f].verts))

    # --- przenikania -----------------------------------------------------
    def _bbox(self, parts):
        pts = np.array([self.V[i] for f in self.faces if f.part in parts for i in f.verts])
        return pts.min(axis=0), pts.max(axis=0)

    def trim(self, parts: set, solid: "Mesh", solid_parts: set, attach_id: int) -> None:
        """Odcina z części `parts` wszystko, co leży wewnątrz zamkniętej bryły `solid_parts`.
        Powstałe krawędzie otwarte to miejsce doklejenia do tamtej bryły (ząbki + obrys)."""
        lo, hi = solid._bbox(solid_parts)
        segs = {}   # linie rozcięcia zapisane geometrycznie — krawędzie mogą zostać podzielone
        for pi in parts:
            segs[pi] = [(self.V[a].copy(), self.V[b].copy()) for a, b in self.parts[pi].cuts]
        old, self.faces = self.faces, []
        for f in old:
            pts = np.array([self.V[i] for i in f.verts])
            if f.part not in parts or (pts.max(axis=0) < lo).any() or (pts.min(axis=0) > hi).any():
                self.faces.append(f)
                continue
            self.faces.append(f)
            fi = len(self.faces) - 1
            o, u, v, n = self.face_frame(fi)
            poly = Polygon(self.face_local(fi))
            self.faces.pop()
            sec = solid.slice(o, n, u, v, solid_parts)
            if sec.is_empty or not sec.intersects(poly):
                self.faces.append(f)
                continue
            keep = poly.difference(sec)
            for g in getattr(keep, "geoms", [keep]):
                if g.geom_type == "Polygon" and g.area > 1e-4:
                    ring = list(g.exterior.coords)[:-1]
                    if g.exterior.is_ccw is False:
                        ring.reverse()
                    self.add_face([o + u * x + v * y for x, y in ring], f.part, f.color)
        for key, lst in self.edges().items():
            if len(lst) == 1 and self.faces[lst[0][0]].part in parts and key not in self.attach:
                self.attach[key] = attach_id
        for pi in parts:
            cuts = set()
            for key in self.edges():
                for a, b in segs[pi]:
                    d, L = b - a, float(np.linalg.norm(b - a))
                    if all(np.linalg.norm(np.cross(self.V[i] - a, d)) / L < 1e-6
                           and -1e-6 <= float((self.V[i] - a) @ d) / L <= L + 1e-6 for i in key):
                        cuts.add(key)
            self.parts[pi].cuts = cuts

    def drop_small_parts(self, parts: set, min_area: float, attach_id: int) -> None:
        """Usuwa części, z których po docięciu zostały tylko okruchy (np. resztka denka nasady)."""
        area: dict = {}
        for fi, f in enumerate(self.faces):
            if f.part in parts:
                area[f.part] = area.get(f.part, 0.0) + Polygon(self.face_local(fi)).area
        gone = {pi for pi, a in area.items() if a < min_area}
        if gone:
            self.faces = [f for f in self.faces if f.part not in gone]
            for key, lst in self.edges().items():
                if len(lst) == 1 and key not in self.attach:
                    self.attach[key] = attach_id

    def imprint(self, parts: set, tool: "Mesh", tool_parts: set) -> list:
        """Ślad bryły `tool_parts` na ścianach `parts`: [(ściana, [łamane w układzie ściany])]."""
        lo, hi = tool._bbox(tool_parts)
        out = []
        for fi, f in enumerate(self.faces):
            if f.part not in parts:
                continue
            pts = self.face_points(fi)
            if (pts.max(axis=0) < lo).any() or (pts.min(axis=0) > hi).any():
                continue
            o, u, v, n = self.face_frame(fi)
            sec = tool.slice(o, n, u, v, tool_parts)
            if sec.is_empty:
                continue
            hit = sec.boundary.intersection(Polygon(self.face_local(fi)))
            lines = [np.array(g.coords) for g in getattr(hit, "geoms", [hit])
                     if g.geom_type == "LineString" and g.length > 1e-4]
            if lines:
                out.append((fi, lines))
        return out

    def _volume(self, fids) -> float:
        vol = 0.0
        for f in fids:
            p = [self.V[i] for i in self.faces[f].verts]
            for i in range(1, len(p) - 1):
                vol += np.dot(p[0], np.cross(p[i], p[i + 1])) / 6.0
        return vol

    def volume(self) -> float:
        return self._volume(range(len(self.faces)))

    # --- geometria ścian -------------------------------------------------
    def face_points(self, f: int) -> np.ndarray:
        return np.array([self.V[i] for i in self.faces[f].verts])

    def face_normal(self, f: int) -> np.ndarray:
        p = self.face_points(f)
        n = np.zeros(3)
        for i in range(len(p)):
            a, b = p[i], p[(i + 1) % len(p)]
            n += np.cross(a, b)
        return n / np.linalg.norm(n)

    def face_frame(self, f: int):
        """(początek, u, v, n) — układ w płaszczyźnie ściany; (u, v) lewoskrętne patrząc z zewnątrz."""
        p = self.face_points(f)
        n = self.face_normal(f)
        u = p[1] - p[0]
        u = u - n * np.dot(u, n)
        u /= np.linalg.norm(u)
        return p[0], u, np.cross(n, u), n

    def face_local(self, f: int) -> np.ndarray:
        o, u, v, _ = self.face_frame(f)
        d = self.face_points(f) - o
        return np.stack([d @ u, d @ v], axis=1)

    # --- przekroje -------------------------------------------------------
    def slice(self, origin, normal, u, v, parts=None):
        """Przekrój bryły płaszczyzną. Zwraca geometrię shapely we współrzędnych (u, v)."""
        origin, normal, u, v = (np.asarray(a, float) for a in (origin, normal, u, v))
        d = {}
        segs = []
        for fi, f in enumerate(self.faces):
            if parts is not None and f.part not in parts:
                continue
            cr = []
            n = len(f.verts)
            for i in range(n):
                a, b = f.verts[i], f.verts[(i + 1) % n]
                for w in (a, b):
                    if w not in d:
                        d[w] = float(np.dot(self.V[w] - origin, normal))
                if (d[a] >= 0) != (d[b] >= 0):
                    t = d[a] / (d[a] - d[b])
                    p = self.V[a] + t * (self.V[b] - self.V[a])
                    cr.append((ekey(a, b), np.array([np.dot(p - origin, u), np.dot(p - origin, v)])))
            if len(cr) > 2:  # ściana niewypukła — parujemy punkty wzdłuż linii cięcia
                dirv = cr[-1][1] - cr[0][1]
                cr.sort(key=lambda c: float(np.dot(c[1], dirv)))
            for i in range(0, len(cr) - 1, 2):
                segs.append((cr[i], cr[i + 1]))
        adj: dict = {}
        for si, (a, b) in enumerate(segs):
            adj.setdefault(a[0], []).append(si)
            adj.setdefault(b[0], []).append(si)
        used = [False] * len(segs)
        polys = []
        for s0 in range(len(segs)):
            if used[s0]:
                continue
            loop = []
            si, key = s0, segs[s0][0][0]
            while not used[si]:
                used[si] = True
                a, b = segs[si]
                if a[0] == key:
                    loop.append(a[1])
                    key = b[0]
                else:
                    loop.append(b[1])
                    key = a[0]
                nxt = [s for s in adj[key] if not used[s]]
                if not nxt:
                    break
                si = nxt[0]
            if len(loop) >= 3:
                pg = Polygon(loop).buffer(0)
                if not pg.is_empty:
                    polys.append(pg)
        return unary_union(polys) if polys else Polygon()


def _planar(pts, tol=1e-7) -> bool:
    p = [np.asarray(q, float) for q in pts]
    n = np.cross(p[2] - p[0], p[3] - p[1])
    ln = np.linalg.norm(n)
    if ln < 1e-12:
        return True
    n /= ln
    scale = max(np.linalg.norm(p[2] - p[0]), np.linalg.norm(p[3] - p[1]), 1.0)
    return all(abs(np.dot(q - p[0], n)) < tol * scale for q in p)
