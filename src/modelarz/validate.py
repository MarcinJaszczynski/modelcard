"""Kontrole jakości — te same w testach, w CLI i w interfejsie."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import Polygon, box

from .layout import GAP, printable
from .project import Project
from .seams import MIN_TAB_EDGE

TOL = 1e-6


@dataclass
class Check:
    name: str
    ok: bool
    detail: str

    def __post_init__(self):
        self.ok = bool(self.ok)   # wyniki numpy nie serializują się do JSON


def validate(pr: Project) -> list[Check]:
    mesh = pr.model.mesh
    out = []
    placement = {id(it.ref): it.placement for it in pr.items}

    # 1. izometria: każda krawędź każdej ściany na arkuszu ma długość z bryły
    worst = 0.0
    for pc in pr.pieces:
        pl = placement[id(pc)]
        for pf in pc.faces:
            p3 = mesh.face_points(pf.face)
            p2 = pl.apply(pf.pts)
            n = len(p3)
            for i in range(n):
                for j in range(i + 1, n):
                    worst = max(worst, abs(np.linalg.norm(p3[i] - p3[j]) - np.linalg.norm(p2[i] - p2[j])))
    out.append(Check("Skala 1:1 i wierność rozwinięć", worst < TOL,
                     f"największa różnica odległości bryła–arkusz: {worst:.2e} mm"))

    # 2. sparowane krawędzie szwów mają równe długości
    worst, pairs = 0.0, 0
    for pi, pc in enumerate(pr.pieces):
        pl = placement[id(pc)]
        for be in pc.boundary:
            if be.partner is None:
                continue
            qi, j = be.partner
            other = pr.pieces[qi].boundary[j]
            la = np.linalg.norm(np.subtract(*pl.apply([be.a, be.b])))
            lb = np.linalg.norm(np.subtract(*placement[id(pr.pieces[qi])].apply([other.a, other.b])))
            l3 = np.linalg.norm(mesh.V[be.key[0]] - mesh.V[be.key[1]])
            worst = max(worst, abs(la - lb), abs(la - l3))
            pairs += 1
    out.append(Check("Długości sklejanych krawędzi", worst < TOL,
                     f"{pairs // 2} par krawędzi, największa różnica {worst:.2e} mm"))

    # 3. obrysy bez samoprzecięć, ściany nie nachodzą na siebie
    bad = []
    for pc in pr.pieces:
        area = sum(Polygon(pf.pts).area for pf in pc.faces)
        ol = pc.shape
        if not (pc.body.is_valid and pc.body.exterior.is_simple and abs(pc.body.area - area) < 1e-4
                and ol.geom_type == "Polygon" and ol.is_valid):
            bad.append(pc.label)
    for it in pr.items:
        if it.kind == "plate" and not (it.outline.geom_type == "Polygon" and it.outline.is_valid):
            bad.append(it.label)
    out.append(Check("Obrysy bez samoprzecięć", not bad,
                     "wszystkie obrysy poprawne" if not bad else f"błędne części: {', '.join(bad)}"))

    # 4. zakładki: każdy szew ma zakładki po dokładnie jednej stronie
    problems = sum(sm.problems for sm in pr.seams)
    uncovered = []
    for sm in pr.seams:
        short = sum(np.linalg.norm(mesh.V[k[0]] - mesh.V[k[1]]) for k in sm.keys
                    if np.linalg.norm(mesh.V[k[0]] - mesh.V[k[1]]) < MIN_TAB_EDGE)
        if sm.tabbed_length < 0.8 * (sm.length - short) - 1e-6:
            uncovered.append(str(sm.number))
    out.append(Check("Zakładki na szwach", problems == 0 and not uncovered,
                     f"{len(pr.seams)} szwów, {sum(len(pc.tabs) for pc in pr.pieces)} zakładek"
                     + (f"; kolizje: {problems}" if problems else "")
                     + (f"; szwy bez pełnych zakładek: {', '.join(uncovered)}" if uncovered else "")))

    # 5. znaczniki miejsc klejenia leżą w całości na ścianach
    bad = [pr.model.marks[i].label for i, (got, exp) in enumerate(pr.mark_lengths) if got < exp - 1e-3]
    if pr.mark_lengths:
        out.append(Check("Obrysy miejsc klejenia", not bad,
                         f"{len(pr.mark_lengths)} znaczników przeniesionych na arkusz" if not bad
                         else f"nie mieszczą się na ścianach: {', '.join(bad)}"))

    # 6. szkielet mieści się wewnątrz poszycia
    bad = [pl.label for pl in pr.model.plates if not pl.poly.within(pl.limit.buffer(1e-6))]
    if pr.model.plates:
        out.append(Check("Szkielet wewnątrz bryły", not bad,
                         f"{len(pr.model.plates)} płyt" if not bad else f"wystają: {', '.join(bad)}"))

    # 7. arkusze: części w polu wydruku, bez nachodzenia
    x0, y0, x1, y1 = printable(pr.page)
    area = box(x0 - 1e-6, y0 - 1e-6, x1 + 1e-6, y1 + 1e-6)
    outside, overlap = [], []
    placed = [(it, it.placement.geom(it.outline)) for it in pr.items]
    for it, g in placed:
        if not g.within(area):
            outside.append(it.label)
    for a in range(len(placed)):
        for b in range(a + 1, len(placed)):
            if placed[a][0].placement.page == placed[b][0].placement.page \
                    and placed[a][1].distance(placed[b][1]) < GAP - 1e-3:
                overlap.append(f"{placed[a][0].label}/{placed[b][0].label}")
    out.append(Check("Rozmieszczenie na arkuszach", not outside and not overlap,
                     f"{len(pr.items)} części na {len(pr.sheets)} arkuszach {pr.page}, odstęp ≥ {GAP:g} mm"
                     + (f"; poza polem: {', '.join(outside)}" if outside else "")
                     + (f"; za blisko: {', '.join(overlap)}" if overlap else "")))
    return out
