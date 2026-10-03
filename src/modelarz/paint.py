"""Malowanie: warstwy opisane na bryle (rzuty z boku / z góry / z dołu albo pasy wzdłuż osi)
są przenoszone na każdą ścianę rozwinięcia przekształceniem afinicznym — kamuflaż, znaki
i linie podziału blach trafiają więc na arkusz dokładnie tam, gdzie leżą na modelu."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

VIEWS = {"side": (0, 2, 1), "top": (0, 1, 2), "bottom": (0, 1, 2), "front": (1, 2, 0), "back": (1, 2, 0)}   # (oś u, oś v, oś normalnej)
AXES = {"x": 0, "y": 1, "z": 2}
BIG = 1e5


@dataclass
class Layer:
    kind: str            # 'fill' | 'line'
    view: str            # 'side' | 'top' | 'bottom' | 'x' | 'y' | 'z'
    geom: object         # geometria shapely w mm (rzuty), zakres (lo, hi) albo wartość (pasy), None = cała ściana
    color: str
    width: float = 0.3   # grubość linii na papierze [pt]
    groups: tuple | None = None
    min_dot: float = 0.25
    side: str = "both"   # dla rzutu z boku: 'left' (y<0), 'right' (y>0), 'both'
    alpha: float = 1.0   # < 1: laserunek (cieniowanie, zabrudzenia)
    dash: tuple | None = None   # np. rząd nitów
    text: str = ""       # napis (kind == 'text'); geom = (x, y) środka, width = wysokość liter w mm


def _star(cx, cy, r):
    pts = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.382
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return Polygon(pts)


def _insignia(kind, cx, cy, size):
    """[(geometria, kolor)] w metrach, od spodu do wierzchu."""
    h = size / 2
    if kind == "balkenkreuz":
        cross = lambda w, l: unary_union([box(cx - l, cy - w, cx + l, cy + w), box(cx - w, cy - l, cx + w, cy + l)])
        return [(cross(h * 0.42, h), "#f4f4f0"), (cross(h * 0.20, h), "#141414")]
    if kind == "us_star":
        blue, white = "#1b2d5c", "#f4f4f0"
        bars = box(cx - 2 * h, cy - h * 0.25, cx + 2 * h, cy + h * 0.25)
        return [(bars.buffer(h * 0.08, join_style="mitre"), blue), (bars, white),
                (Point(cx, cy).buffer(h, 32), blue), (_star(cx, cy, h), white)]
    if kind == "roundel_pl":   # szachownica
        q = lambda i, j: box(cx + (i - 1) * h, cy + (j - 1) * h, cx + i * h, cy + j * h)
        return [(box(cx - h, cy - h, cx + h, cy + h).buffer(h * 0.12, join_style="mitre"), "#c8102e"),
                (box(cx - h, cy - h, cx + h, cy + h), "#f4f4f0"), (unary_union([q(0, 1), q(1, 0)]), "#c8102e")]
    raise ValueError(f"nieznany znak: {kind}")


def layers_from_spec(items: list, s: float) -> list[Layer]:
    """Zamienia opis malowania (jednostki: metry oryginału) na warstwy w mm modelu."""
    out = []
    for it in items:
        common = dict(groups=tuple(it["groups"]) if it.get("groups") else None,
                      side=it.get("side", "both"), alpha=it.get("alpha", 1.0),
                      dash=tuple(it["dash"]) if it.get("dash") else None)
        view = it["view"]
        if "min_dot" in it:
            common["min_dot"] = it["min_dot"]
        elif view in ("top", "bottom"):
            common["min_dot"] = 0.12
        mm = lambda g: affinity.scale(g, s, s, origin=(0, 0))

        def both(g):
            return unary_union([g, affinity.scale(g, 1, -1, origin=(0, 0))]) if it.get("mirror") else g
        if view in AXES:
            if "range" in it:
                out.append(Layer("fill", view, (it["range"][0] * s, it["range"][1] * s), it["color"], **common))
            else:
                out.append(Layer("line", view, it["at"] * s, it.get("color", "#2c3136"), it.get("width", 0.3), **common))
        elif "text" in it:
            out.append(Layer("text", view, (it["at"][0] * s, it["at"][1] * s), it.get("color", "#f4f4f0"),
                             it["size"] * s, text=str(it["text"]), **common))
        elif "insignia" in it:
            for g, col in _insignia(it["insignia"], it["at"][0], it["at"][1], it["size"]):
                out.append(Layer("fill", view, mm(both(g)), col, **common))
        elif "line" in it:
            g = LineString(it["line"])
            if it.get("mirror"):
                g = unary_union([g, affinity.scale(g, 1, -1, origin=(0, 0))])
            out.append(Layer("line", view, mm(g), it.get("color", "#3a3f44"), it.get("width", 0.3), **common))
        elif it.get("polygon") == "all":
            out.append(Layer("fill", view, None, it["color"], **common))
        elif "rect" in it:
            x0, y0, x1, y1 = it["rect"]
            out.append(Layer("fill", view, mm(both(box(x0, y0, x1, y1))), it["color"], **common))
        else:
            out.append(Layer("fill", view, mm(both(Polygon(it["polygon"]).buffer(0))), it["color"], **common))
    return out


def _applies(layer: Layer, n, group) -> bool:
    if layer.groups and group not in layer.groups:
        return False
    if layer.view == "side":
        if abs(n[1]) < layer.min_dot:
            return False
        return layer.side == "both" or (layer.side == "right") == (n[1] > 0)
    if layer.view == "top":
        return n[2] >= layer.min_dot
    if layer.view == "bottom":
        return -n[2] >= layer.min_dot
    if layer.view == "front":
        return -n[0] >= layer.min_dot
    if layer.view == "back":
        return n[0] >= layer.min_dot
    return True


def _on_face(layer: Layer, P, Q, poly):
    """Część warstwy leżąca na ścianie, we współrzędnych rozwinięcia. P: punkty 3D, Q: punkty 2D."""
    ones = np.ones((len(Q), 1))
    if layer.view in AXES:
        c = P[:, AXES[layer.view]]
        g = np.linalg.lstsq(np.hstack([Q, ones]), c, rcond=None)[0]
        gl = float(np.hypot(g[0], g[1]))
        if layer.kind == "fill":
            lo, hi = layer.geom
            if gl < 1e-9:
                return poly if lo <= g[2] <= hi else None
            gh, hh = g[:2] / gl, np.array([-g[1], g[0]]) / gl
            a, b = gh * (lo - g[2]) / gl, gh * (hi - g[2]) / gl
            return Polygon([a - hh * BIG, a + hh * BIG, b + hh * BIG, b - hh * BIG]).intersection(poly)
        if gl < 1e-9:
            return None
        gh, hh = g[:2] / gl, np.array([-g[1], g[0]]) / gl
        a = gh * (layer.geom - g[2]) / gl
        return LineString([a - hh * BIG, a + hh * BIG]).intersection(poly)
    if layer.geom is None:
        return poly
    u, v, _ = VIEWS[layer.view]
    proj = P[:, [u, v]]
    b = layer.geom.bounds
    if proj[:, 0].max() < b[0] or proj[:, 0].min() > b[2] or proj[:, 1].max() < b[1] or proj[:, 1].min() > b[3]:
        return None
    X = np.linalg.lstsq(np.hstack([proj, ones]), Q, rcond=None)[0]
    g = affinity.affine_transform(layer.geom, [X[0, 0], X[1, 0], X[0, 1], X[1, 1], X[2, 0], X[2, 1]])
    return g.intersection(poly)


def apply_paint(mesh, pieces, layers: list[Layer]) -> None:
    """Wypełnia pc.paint = [(wielokąt, kolor)] i pc.paint_lines = [(łamana, kolor, grubość)]."""
    for pc in pieces:
        group = mesh.parts[pc.part].group
        for pf in pc.faces:
            P = mesh.face_points(pf.face)
            poly = Polygon(pf.pts)
            for layer in layers:
                if not _applies(layer, pf.n3, group):
                    continue
                if layer.kind == "text":
                    u, v, nax = VIEWS[layer.view]
                    cx, cy = layer.geom
                    proj = P[:, [u, v]].copy()
                    # napis czytany z zewnątrz: po stronie, gdzie rzut jest lustrzany, odbijamy go wokół środka
                    if (layer.view == "side" and pf.n3[1] > 0) or (layer.view in ("bottom", "front")):
                        proj[:, 0] = 2 * cx - proj[:, 0]
                    half = 0.35 * layer.width * len(layer.text) + 1
                    if proj[:, 0].max() < cx - half or proj[:, 0].min() > cx + half \
                            or proj[:, 1].max() < cy - layer.width or proj[:, 1].min() > cy + layer.width:
                        continue
                    X = np.linalg.lstsq(np.hstack([proj, np.ones((len(proj), 1))]), pf.pts, rcond=None)[0]
                    pc.paint_text.append((pf.pts, (X[0, 0], X[0, 1], X[1, 0], X[1, 1], X[2, 0], X[2, 1]),
                                          layer.text, layer.width, layer.color, cx, cy))
                    continue
                hit = _on_face(layer, P, pf.pts, poly)
                if hit is None or hit.is_empty:
                    continue
                for g in getattr(hit, "geoms", [hit]):
                    if layer.kind == "fill" and g.geom_type == "Polygon" and g.area > 1e-4:
                        pc.paint.append((np.array(g.exterior.coords), layer.color, layer.alpha))
                    elif layer.kind == "line" and g.geom_type == "LineString" and g.length > 1e-3:
                        pc.paint_lines.append((np.array(g.coords), layer.color, layer.width, layer.alpha, layer.dash))


def color_faces(mesh, layers: list[Layer]) -> None:
    """Kolor ściany w jej środku — do podglądu 3D i jako podkład pod dokładne malowanie."""
    for fi, f in enumerate(mesh.faces):
        part = mesh.parts[f.part]
        if part.virtual:
            continue
        P = mesh.face_points(fi)
        c, n = P.mean(axis=0), mesh.face_normal(fi)
        for layer in layers:
            if layer.kind != "fill" or layer.alpha < 0.99 or not _applies(layer, n, part.group):
                continue
            if layer.view in AXES:
                inside = layer.geom[0] <= c[AXES[layer.view]] <= layer.geom[1]
            else:
                u, v, _ = VIEWS[layer.view]
                inside = layer.geom is None or layer.geom.contains(Point(c[u], c[v]))
            if inside:
                f.shade = layer.color


RIVETS = (0.01, 1.3)   # kropki co 1,3 pt (rysowane z zaokrąglonym końcem linii)


def shade_by_form(mesh, pieces, strength: float = 1.0) -> None:
    """Uplastycznienie: ściany zwrócone w dół i na boki są lekko przyciemniane, górne rozjaśniane."""
    for pc in pieces:
        if mesh.parts[pc.part].group in ("canopy",):
            continue
        for pf in pc.faces:
            nz = float(pf.n3[2])
            dark = 0.13 * strength * ((1 - nz) / 2) ** 1.3
            pts = np.vstack([pf.pts, pf.pts[:1]])
            if dark > 0.01:
                pc.paint.append((pts, "#000000", dark))
            elif nz > 0.9:
                pc.paint.append((pts, "#ffffff", 0.06 * strength))


def panel_line(view, line, groups, **kw):
    """Linia podziału blach: szeroki cień + cienka kreska (opis w metrach, jak w pliku samolotu)."""
    base = dict(view=view, groups=groups, **kw)
    return [dict(base, line=line, color="#000000", width=2.4, alpha=0.10),
            dict(base, line=line, color="#2c3136", width=0.3, alpha=0.9)]


def rivet_line(view, line, groups, **kw):
    return [dict(view=view, groups=groups, line=line, color="#20252a", width=0.45, alpha=0.55, dash=RIVETS, **kw)]
