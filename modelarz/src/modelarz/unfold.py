"""Rozwijanie części na płaszczyznę: każda ściana jest przenoszona sztywno (izometrycznie),
więc długości wszystkich krawędzi na arkuszu są dokładnie takie jak na bryle."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import LineString, Polygon

from .mesh import Mesh, ekey

FLAT_DEG = 0.5          # poniżej tego kąta ściany uznajemy za współpłaszczyznowe
SMOOTH_FOLD_DEG = 35.0  # na powierzchniach zwijanych rysujemy tylko ostrzejsze załamania


@dataclass
class PlacedFace:
    face: int
    pts: np.ndarray       # (n, 2) położenie wierzchołków na rozwinięciu
    o3: np.ndarray        # układ ściany w 3D
    u3: np.ndarray
    v3: np.ndarray
    n3: np.ndarray
    R: np.ndarray         # lokalne 2D -> rozwinięcie: R @ (l - l0) + p0
    l0: np.ndarray
    p0: np.ndarray

    def map3d(self, p) -> np.ndarray:
        d = np.asarray(p, float) - self.o3
        return self.R @ (np.array([d @ self.u3, d @ self.v3]) - self.l0) + self.p0


@dataclass
class BEdge:
    a: np.ndarray
    b: np.ndarray
    key: tuple
    face: int
    partner: tuple | None = None   # (indeks rozwinięcia, pozycja na obrysie)
    vpart: int | None = None       # część wirtualna po drugiej stronie
    seam: int = 0
    tabbed: bool = False

    @property
    def length(self) -> float:
        return float(np.linalg.norm(self.b - self.a))


@dataclass
class Fold:
    a: np.ndarray
    b: np.ndarray
    kind: str     # 'mountain' | 'valley'
    angle: float  # stopnie
    draw: bool


@dataclass
class Piece:
    part: int
    label: str = ""
    faces: list = field(default_factory=list)
    folds: list = field(default_factory=list)
    boundary: list = field(default_factory=list)
    body: Polygon | None = None
    tabs: list = field(default_factory=list)        # [(Polygon, a, b)]
    seam_labels: list = field(default_factory=list)  # [(numer, punkt)]
    marks: list = field(default_factory=list)        # [(styl, etykieta, [odcinki 2D])]
    tab_problems: int = 0
    _spot: tuple | None = None

    @property
    def spot(self):
        """Miejsce na numer części: środek i promień największego koła wpisanego."""
        if self._spot is None:
            import shapely
            try:
                (cx, cy), (bx, by) = shapely.maximum_inscribed_circle(self.body, tolerance=0.2).coords
                self._spot = ((cx, cy), math.hypot(cx - bx, cy - by))
            except Exception:
                q = self.body.representative_point()
                self._spot = ((q.x, q.y), 2.0)
        return self._spot

    @property
    def outline(self):
        from shapely.ops import unary_union
        # minimalne pogrubienie zakładek skleja je numerycznie z korpusem (tylko do pakowania)
        return unary_union([self.body] + [t[0].buffer(0.02, join_style="mitre") for t in self.tabs])


def _rot(ang: float) -> np.ndarray:
    c, s = math.cos(ang), math.sin(ang)
    return np.array([[c, -s], [s, c]])


def unfold_part(mesh: Mesh, part_idx: int, edges: dict, max_size=None) -> list[Piece]:
    part = mesh.parts[part_idx]
    fids = [i for i, f in enumerate(mesh.faces) if f.part == part_idx]
    todo = dict.fromkeys(fids)
    pieces = []
    while todo:
        root = next(iter(todo))
        del todo[root]
        placed: dict[int, PlacedFace] = {}
        polys: dict[int, Polygon] = {}

        def put(f, R, l0, p0):
            o, u, v, n = mesh.face_frame(f)
            loc = mesh.face_local(f)
            pts = (loc - l0) @ R.T + p0
            return PlacedFace(f, pts, o, u, v, n, R, l0, p0)

        placed[root] = put(root, np.eye(2), np.zeros(2), np.zeros(2))
        polys[root] = Polygon(placed[root].pts)
        tree = {}
        queue = [root]
        while queue:
            f = queue.pop(0)
            vs = mesh.faces[f].verts
            n = len(vs)
            for i in range(n):
                key = ekey(vs[i], vs[(i + 1) % n])
                if key in part.cuts:
                    continue
                for g, j in edges[key]:
                    if g == f or g not in todo:
                        continue
                    pa, pb = placed[f].pts[i], placed[f].pts[(i + 1) % n]
                    loc = mesh.face_local(g)
                    m = len(loc)
                    # w ścianie g ta krawędź biegnie w przeciwną stronę: j -> pb, j+1 -> pa
                    lj, lj1 = loc[j], loc[(j + 1) % m]
                    ang = math.atan2(*(pa - pb)[::-1]) - math.atan2(*(lj1 - lj)[::-1])
                    cand = put(g, _rot(ang), lj, pb)
                    cpoly = Polygon(cand.pts)
                    if any(h != f and cpoly.intersects(q) and cpoly.intersection(q).area > 1e-6
                           for h, q in polys.items()):
                        continue  # nachodziłoby na siebie — ta ściana trafi do innego rozwinięcia
                    if max_size and not _fits([q.pts for q in placed.values()] + [cand.pts], max_size):
                        continue  # rozwinięcie nie zmieściłoby się na arkuszu — dzielimy część
                    placed[g], polys[g] = cand, cpoly
                    del todo[g]
                    tree[key] = (f, i, g)
                    queue.append(g)

        pc = Piece(part=part_idx, faces=list(placed.values()))
        for key, (f, i, g) in tree.items():
            nf, ng = placed[f].n3, placed[g].n3
            ang = math.degrees(math.acos(max(-1.0, min(1.0, float(nf @ ng)))))
            if ang < FLAT_DEG:
                continue
            cg = mesh.face_points(g).mean(axis=0)
            convex = float((cg - mesh.V[key[0]]) @ nf) < 0
            n = len(mesh.faces[f].verts)
            pc.folds.append(Fold(placed[f].pts[i], placed[f].pts[(i + 1) % n],
                                 "mountain" if convex else "valley", ang,
                                 ang > (SMOOTH_FOLD_DEG if part.smooth else FLAT_DEG)))
        raw = []
        for f, pf in placed.items():
            vs = mesh.faces[f].verts
            n = len(vs)
            for i in range(n):
                key = ekey(vs[i], vs[(i + 1) % n])
                if key not in tree:
                    raw.append(BEdge(pf.pts[i], pf.pts[(i + 1) % n], key, f))
        pc.boundary = _chain(raw)
        pc.body = Polygon([e.a for e in pc.boundary])
        pieces.append(pc)
    return pieces


def _fits(pts_list, max_size) -> bool:
    from shapely.geometry import MultiPoint

    from .layout import mrr
    r = mrr(MultiPoint(np.vstack(pts_list)))
    if r.geom_type != "Polygon":
        return True
    c = list(r.exterior.coords)
    a, b = sorted((math.dist(c[0], c[1]), math.dist(c[1], c[2])))
    return a <= min(max_size) and b <= max(max_size)


def _chain(raw: list[BEdge]) -> list[BEdge]:
    """Układa krawędzie brzegowe w zamkniętą pętlę (przeciwnie do wskazówek zegara)."""
    def k(p):
        return (round(float(p[0]), 4), round(float(p[1]), 4))
    starts: dict = {}
    for e in raw:
        starts.setdefault(k(e.a), []).append(e)
    loops, left = [], {id(e) for e in raw}
    for e0 in raw:
        if id(e0) not in left:
            continue
        loop, e = [], e0
        while e is not None and id(e) in left:
            left.discard(id(e))
            loop.append(e)
            nxt = [c for c in starts.get(k(e.b), []) if id(c) in left]
            if len(nxt) > 1:  # punkt styku — wybieramy najbardziej „w prawo”, by nie zamknąć pętli za wcześnie
                d = e.b - e.a
                nxt.sort(key=lambda c: math.atan2(d[0] * (c.b - c.a)[1] - d[1] * (c.b - c.a)[0],
                                                  float(d @ (c.b - c.a))))
            e = nxt[0] if nxt else None
        loops.append(loop)
    loops.sort(key=lambda lp: -abs(Polygon([e.a for e in lp]).area) if len(lp) >= 3 else 0)
    return loops[0]


def map_marks(mesh: Mesh, pieces: list[Piece], marks: list) -> list[float]:
    """Przenosi znaczniki (łamane 3D leżące na ścianach) na rozwinięcia.
    Zwraca dla każdego znacznika długość, którą udało się odwzorować."""
    mapped = []
    for mk in marks:
        pts = [np.asarray(p, float) for p in mk.pts]
        segs = list(zip(pts, pts[1:] + ([pts[0]] if mk.closed else [])))
        total = 0.0
        for pc in pieces:
            out = []
            for pf in pc.faces:
                poly = None
                for a, b in segs:
                    if abs((a - pf.o3) @ pf.n3) > 1e-4 or abs((b - pf.o3) @ pf.n3) > 1e-4:
                        continue
                    if mk.normal is not None and float(np.asarray(mk.normal) @ pf.n3) < 0.99:
                        continue
                    if poly is None:
                        poly = Polygon(pf.pts)
                    hit = LineString([pf.map3d(a), pf.map3d(b)]).intersection(poly)
                    for g in getattr(hit, "geoms", [hit]):
                        if g.geom_type == "LineString" and g.length > 1e-6:
                            out.append(np.array(g.coords))
                            total += g.length
            if out:
                pc.marks.append((mk.style, mk.label, out))
        mapped.append(total)
    return mapped
