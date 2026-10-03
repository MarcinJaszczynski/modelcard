"""Cały potok: bryła -> rozwinięcia -> szwy i zakładki -> znaczniki -> arkusze."""
from __future__ import annotations

from dataclasses import dataclass, field

from .layout import Placement, pack, printable
from .models.base import Model
from .paint import apply_paint, color_faces, shade_by_form
from .seams import Seam, build_seams
from shapely.geometry import Point
from shapely.ops import unary_union

from .unfold import BADGE_R, Piece, badge_spot, map_marks, unfold_part


@dataclass
class Item:
    label: str
    name: str
    kind: str            # 'skin' | 'plate'
    ref: object          # Piece albo Plate
    outline: object
    placement: Placement | None = None


@dataclass
class Project:
    model: Model
    page: str
    pieces: list[Piece]
    seams: list[Seam]
    items: list[Item]
    sheets: list[tuple]              # [(tytuł grupy, numer strony w grupie, liczba stron grupy)]
    mark_lengths: list[tuple] = field(default_factory=list)   # (odwzorowana, oczekiwana)
    steps: list[str] = field(default_factory=list)


def build_project(model: Model, page: str = "A4", tab_h: float = 5.0) -> Project:
    mesh = model.mesh
    mesh.orient()
    edges = mesh.edges()

    x0, y0, x1, y1 = printable(page)
    room = (x1 - x0 - 2 * tab_h - 7, y1 - y0 - 2 * tab_h - 7)   # zapas na zakładki i numer części
    pieces: list[Piece] = []
    num = 0
    for pi, part in enumerate(mesh.parts):
        if part.virtual:
            continue
        num += 1
        part.number = num
        pcs = unfold_part(mesh, pi, edges, room)
        for k, pc in enumerate(pcs):
            pc.label = str(num) if len(pcs) == 1 else f"{num}{'abcdefghijklmnop'[k]}"
        pieces.extend(pcs)

    seams = build_seams(mesh, pieces, tab_h)

    for mk in model.marks:
        if mk.seam_of is not None:
            nums = [str(sm.number) for sm in seams if sm.virtual_part == mk.seam_of]
            mk.label = f"szew {', '.join(nums)}"
    mapped = map_marks(mesh, pieces, model.marks)
    where = {pf.face: (pc, pf) for pc in pieces for pf in pc.faces}
    for style, label, attach_id, hits in model.face_marks:
        if attach_id is not None:
            nums = [str(sm.number) for sm in seams if sm.virtual_part == attach_id]
            if nums:
                label = f"szew {', '.join(nums)}" if len(nums) <= 2 else f"szwy {nums[0]}–{nums[-1]}"
        per_piece: dict = {}
        for fi, lines in hits:
            if fi in where:
                pc, pf = where[fi]
                per_piece.setdefault(id(pc), (pc, []))[1].extend((ln - pf.l0) @ pf.R.T + pf.p0 for ln in lines)
        for pc, segs in per_piece.values():
            pc.marks.append((style, label, segs))
    expected = []
    for mk in model.marks:
        pts = list(mk.pts) + ([mk.pts[0]] if mk.closed else [])
        expected.append(sum(float(((_v(a) - _v(b)) ** 2).sum() ** 0.5) for a, b in zip(pts, pts[1:])))

    if model.paint:
        apply_paint(mesh, pieces, model.paint)
        color_faces(mesh, model.paint)
    if model.shading:
        shade_by_form(mesh, pieces, model.shading)

    items = [Item(pc.label, mesh.parts[pc.part].name, "skin", pc, pc.outline) for pc in pieces]
    for fp in model.flats:
        num += 1
        fp.number = num
        fp.badge = badge_spot(fp.poly)
        shape = unary_union([fp.poly, Point(fp.badge[0]).buffer(BADGE_R)])
        items += [Item(str(num), fp.name, "flat", fp, shape) for _ in fp.frames]
    items += [Item(pl.label, pl.name, "plate", pl, pl.poly) for pl in model.plates]
    sheets, offset = [], 0
    groups = (("skin", f"Poszycie — karton ok. {model.paper:g} mm".replace(".", ",")),
              ("plate", f"Szkielet — nakleić na tekturę {model.card:g} mm".replace(".", ",")))
    for kind, title in groups:
        grp = [it for it in items if it.kind == kind or (kind == "skin" and it.kind == "flat")]
        if not grp:
            continue
        pls, n = pack([it.outline for it in grp], page, [f"{it.label} ({it.name})" for it in grp])
        for it, pl in zip(grp, pls):
            pl.page += offset
            it.placement = pl
        sheets += [(title, k + 1, n) for k in range(n)]
        offset += n

    pr = Project(model, page, pieces, seams, items, sheets, list(zip(mapped, expected)))
    pr.steps = _steps(pr)
    return pr


def _v(p):
    import numpy as np
    return np.asarray(p, float)


def _steps(pr: Project) -> list[str]:
    mesh = pr.model.mesh
    steps = []
    for pi, pc in enumerate(pr.pieces):
        closing, joins, attach = [], [], []
        for sm in pr.seams:
            ids = [s[0] for s in sm.sides]
            if pi not in ids:
                continue
            if sm.virtual_part is not None:
                attach.append(str(sm.number))
            elif len(ids) == 2 and ids[0] == ids[1]:
                closing.append(str(sm.number))
            else:
                other = [i for i in ids if i != pi]
                if other and other[0] < pi:
                    joins.append(f"{sm.number} (z częścią {pr.pieces[other[0]].label})")
        txt = f"Część {pc.label} — {mesh.parts[pc.part].name}: wytnij"
        if any(f.draw for f in pc.folds):
            txt += ", zegnij wzdłuż linii"
        elif mesh.parts[pc.part].smooth:
            txt += ", uformuj (zwiń)"
        if closing:
            txt += f"; sklej szwy własne: {', '.join(closing)}"
        if joins:
            txt += f"; doklej szwami: {', '.join(joins)}"
        if attach:
            txt += f"; przyklej ząbkami do obrysu oznaczonego numerem {', '.join(attach)}"
        steps.append(txt + ".")
    for fp in pr.model.flats:
        steps.append(f"Część {fp.number} — {fp.name} ({len(fp.frames)} szt.): {fp.note}.")
    return steps
