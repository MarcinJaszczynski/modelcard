"""Samolot z opisu w danych (plik JSON w `samoloty/`). Wymiary oryginału w metrach, model w mm.

Kadłub to pasy między przekrojami o krzywym obrysie (superelipsa). Płaty, usterzenie i osłona
kabiny są budowane jako zamknięte bryły wchodzące w kadłub, a potem docinane dokładnie do jego
powierzchni: krawędź docięcia dostaje ząbki, a na kadłubie rysowany jest obrys przyklejenia."""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from importlib import resources

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from ..mesh import Mesh
from ..paint import RIVETS, layers_from_spec, panel_line, rivet_line
from ..skeleton import Plate, clip_x, halflap, largest, plate_from_slice
from .base import FlatPart, Mark, Model, P, cap


@dataclass
class AircraftParams:
    scale: float = P("Skala 1:", 33, 24, 100)
    level: int = P("Stopień trudności (1 łatwy – 3 trudny)", 2, 1, 3)
    weather: int = P("Zabrudzenia i ślady eksploatacji (0–3)", 1, 0, 3)
    paper: float = P("Grubość kartonu poszycia [mm]", 0.25, 0.1, 0.6)
    card: float = P("Grubość tektury szkieletu [mm]", 1.0, 0.5, 2.0)


# stopień trudności: gęstość podziału, szkielet, drobne części
LEVELS = {
    1: dict(ring=16, wing=6, tail=5, canopy=4, skeleton=False, ribs=0, gear=False),
    2: dict(ring=24, wing=10, tail=8, canopy=6, skeleton=True, ribs=3, gear=True),
    3: dict(ring=32, wing=14, tail=10, canopy=8, skeleton=True, ribs=5, gear=True),
}
GLASS = "#a9cfe8"


def section(st, s, n):
    """Przekrój kadłuba: superelipsa o osobnym kształcie góry i dołu, zaczynając od środka spodu.
    st = [x, połowa szerokości, góra, dół, wysokość największej szerokości, wykładnik góry, wykładnik dołu]."""
    x, w, zt, zb, zc, et, eb = st[:7]
    pts = []
    for k in range(n):
        a = -math.pi / 2 + 2 * math.pi * k / n
        c, sn = math.cos(a), math.sin(a)
        e = et if sn >= 0 else eb
        y = 0.0 if k in (0, n // 2) else math.copysign(abs(c) ** (2 / e), c) * w
        z = zc + (zt - zc) * abs(sn) ** (2 / e) if sn >= 0 else zc - (zc - zb) * abs(sn) ** (2 / e)
        pts.append((x * s, y * s, z * s))
    return pts


def naca(m, t, camber):
    """Obrys profilu o cięciwie 1: spływ -> góra -> natarcie -> dół."""
    xs = [(1 - math.cos(math.pi * i / m)) / 2 for i in range(m + 1)]
    yt = lambda x: 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    p = 0.4
    yc = lambda x: camber / p**2 * (2 * p * x - x * x) if x < p else camber / (1 - p)**2 * (1 - 2 * p + 2 * p * x - x * x)
    return [(x, yc(x) + yt(x)) for x in reversed(xs)] + [(x, yc(x) - yt(x)) for x in xs[1:-1]]


def add_surface(m: Mesh, name, group, spec, xf, color, s, pts):
    """Płat rozpięty przez kolejne żebra (pierwsze leży wewnątrz kadłuba). Zwraca zbiór części."""
    secs = [list(q) for q in spec["sections"]]
    tan = math.tan(math.radians(spec.get("dihedral", 0)))
    cam = spec.get("camber", 0.0)

    def ring(d):
        xle, y, zc, chord, t = d
        zc = zc + (y - secs[0][1]) * tan
        return [xf(((xle + chord * x) * s, y * s, (zc + chord * z) * s)) for x, z in naca(pts, t, cam)]
    rings = [ring(d) for d in secs]
    parts = set()
    for i in range(len(rings) - 1):
        label = name if len(rings) == 2 else f"{name} {i + 1}"
        part = m.add_part(label, color=color, smooth=True, tab_priority=1, group=group)
        m.loft(rings[i], rings[i + 1], part, cut_at=0)
        parts.add(part)
    for ring_, label, prio in ((rings[-1], "końcówka", -1), (rings[0], "nasada", -2)):
        part = m.add_part(f"{name} – {label}", color=color, tab_priority=prio, group=group)
        cap(m, ring_, part)
        parts.add(part)
    return parts


def add_canopy(m: Mesh, spec, s, n_arc):
    """Osłona kabiny jako zamknięta bryła zagłębiona w grzbiet kadłuba (spód zostanie odcięty)."""
    z0, secs, hw0, h0 = spec["z0"], spec["sections"], spec["hw"], spec["h"]
    if spec.get("profile") == "box":     # oszklenie z płaskich szyb (np. Bf 109)
        top = spec.get("top", 0.7)
        prof = [(1.0, 0.0), (top, 1.0), (-top, 1.0), (-1.0, 0.0)]
    else:                                # osłona kroplowa
        prof = [(math.cos(math.pi * k / n_arc), math.sin(math.pi * k / n_arc)) for k in range(n_arc + 1)]

    def ring(sec):
        x, kw, kh = sec
        return [(x * s, hw0 * kw * py * s, (z0 + h0 * kh * pz) * s) for py, pz in prof] + [(x * s, 0.0, (z0 - 0.3) * s)]
    rings = [ring(sec) for sec in secs]
    parts = set()
    for i in range(len(rings) - 1):
        part = m.add_part(f"Osłona kabiny {i + 1}", color=spec.get("color", GLASS), smooth=True,
                          tab_priority=1, group="canopy")
        m.loft(rings[i], rings[i + 1], part, cut_at=len(prof))
        parts.add(part)
    for ring_, label in ((rings[0], "przód"), (rings[-1], "tył")):   # osobne szybki zamykające
        part = m.add_part(f"Osłona kabiny – {label}", color=spec.get("color", GLASS), tab_priority=-1, group="canopy")
        cap(m, ring_, part)
        parts.add(part)
    return parts


def add_prop(spec, s) -> FlatPart:
    R, r0, chord = spec["radius"] * s, spec.get("hub", 0.2) * s, spec["chord"] * s
    te = []
    for i in range(1, 16):
        t = i / 16
        c = chord * (0.45 + 0.55 * math.sin(math.pi * t ** 0.8)) * (1 if t < 0.8 else math.sqrt(max(0, 1 - ((t - 0.8) / 0.2) ** 2)))
        te.append((r0 + t * (R - r0), -c))
    face = Polygon([(r0, 0), (r0, -chord * 0.45)] + te + [(R, 0)])
    full = unary_union([face, affinity.scale(face, 1, -1, origin=(0, 0))]).buffer(0)
    n, x = spec["blades"], spec.get("x", 0.3) * s
    frames = []
    for k in range(n):
        a = 2 * math.pi * k / n + math.pi / 2
        frames.append((np.array([x, 0, 0.0]), np.array([0, math.cos(a), math.sin(a)]),
                       np.array([0, -math.sin(a), math.cos(a)])))
    tip = box(R - 0.08 * (R - r0), -chord, R, chord).intersection(full)
    return FlatPart("Łopata śmigła", full, face, spec.get("color", "#2b2b2b"), frames, [((r0, 0), (R, 0))],
                    [(tip, spec.get("tip_color", "#e3b324"))],
                    "wytnij, zegnij na pół wzdłuż linii, sklej i wklej nasadą w kołpak")


def add_gear(spec, s, card):
    x, y, zt, L, r = (spec[k] * s for k in ("x", "y", "z_top", "leg", "wheel_r"))
    w = max(2.5, 0.09 * s)
    flats, plates = [], []
    X, Y, Z = np.eye(3)
    legs, tyres = [], []
    for sign in (1, -1):
        legs.append((np.array([x - w / 2, sign * y, zt]), X, -Z))
        c = np.array([x, sign * y, zt - L])
        disc = Point(0, 0).buffer(r, 24)
        plates.append(Plate("KP" if sign > 0 else "KL", f"Koło {'prawe' if sign > 0 else 'lewe'} (rdzeń)",
                            c, X, Z, disc, disc, card))
        tyres += [(c + Y * card / 2, X, Z), (c - Y * card / 2, X, Z)]
    leg = box(0, 0, w, L + r * 0.3)
    flats.append(FlatPart("Goleń podwozia", box(-w, 0, w, L + r * 0.3), leg, "#9aa0a6", legs,
                          [((0, 0), (0, L + r * 0.3))], [], "wytnij, zegnij na pół, sklej; przyklej pod skrzydłem"))
    disc = Point(0, 0).buffer(r, 24)
    flats.append(FlatPart("Koło – okładzina", disc, disc, "#1e1e1e", tyres, [],
                          [(Point(0, 0).buffer(r * 0.45, 24), "#9aa0a6")], "wytnij i naklej z obu stron na rdzeń koła"))
    return flats, plates


def auto_detail(spec: dict, stations: list) -> list:
    """Linie podziału blach i rzędy nitów wyprowadzone z konstrukcji (wręgi, podłużnice, dźwigary, żebra)."""
    L = []
    fus = ["fuselage"]
    xs = [st[0] for st in stations]
    for a, b in zip(xs, xs[1:]):
        mid = (a + b) / 2
        L += [dict(view="x", at=mid, groups=fus, color="#000000", width=2.4, alpha=0.10),
              dict(view="x", at=mid, groups=fus, width=0.3, alpha=0.9)]
        for q in (a + 0.035, b - 0.035, mid + 0.03):
            L.append(dict(view="x", at=q, groups=fus, color="#20252a", width=0.45, alpha=0.55, dash=RIVETS))
    for f in (0.0, 0.55, -0.55):
        line = [[st[0], st[4] + f * ((st[2] - st[4]) if f > 0 else (st[4] - st[3]))] for st in stations]
        L += panel_line("side", line, fus) + rivet_line("side", [[x, z + 0.03] for x, z in line], fus)
    lerp = lambda a, b, t: a + (b - a) * t
    for key, hinge, pitch in (("wing", 0.76, 0.45), ("stab", 0.62, 0.22), ("fin", 0.62, 0.22)):
        secs = spec[key]["sections"]
        root, tip = secs[0], secs[-2]
        views = ("side",) if key == "fin" else ("top", "bottom")
        kw = dict() if key == "fin" else dict(mirror=True, min_dot=0.05)
        pt = lambda frac, t: [lerp(root[0] + frac * root[3], tip[0] + frac * tip[3], t), lerp(root[1], tip[1], t)]
        span = tip[1] - root[1]
        for view in views:
            for frac in (0.12, 0.38):
                L += panel_line(view, [pt(frac, 0), pt(frac, 1)], [key], **kw)
                L += rivet_line(view, [pt(frac + 0.015, 0), pt(frac + 0.015, 1)], [key], **kw)
            L += panel_line(view, [pt(hinge, 0.1), pt(hinge, 1)], [key], **kw)
            L += [dict(view=view, groups=[key], line=[pt(hinge + 0.012, 0.1), pt(hinge + 0.012, 1)],
                       color="#000000", width=3.5, alpha=0.10, **kw)]
            n = max(2, int(span / pitch))
            for i in range(1, n):
                t = i / n
                L += rivet_line(view, [pt(0.03, t), pt(hinge, t)], [key], **kw)
                L += [dict(view=view, groups=[key], line=[pt(hinge, t), pt(0.99, t)], color="#000000",
                           width=1.6, alpha=0.08, **kw)]
    return L


def weathering(spec: dict, stations: list, level: int) -> list:
    """Ślady eksploatacji: okopcenie za rurami wydechowymi, zacieki, otarcia farby przy nasadzie skrzydła."""
    if level <= 0:
        return []
    import random
    rng = random.Random(spec["name"])
    L = []
    fus = ["fuselage"]
    if "exhaust" in spec:
        x0, z, x1 = spec["exhaust"]
        for k in range(3):
            far = x1 + 0.7 + 0.5 * k
            L.append(dict(view="side", groups=fus, color="#1a1512", alpha=0.07 * level,
                          polygon=[[x0, z + 0.05], [x1, z + 0.06], [far, z + 0.16 + 0.04 * k],
                                   [far, z - 0.14 - 0.04 * k], [x1, z - 0.07], [x0, z - 0.05]]))
    x_a, x_b = stations[0][0], stations[-1][0]
    for _ in range(22 * level):
        x, z, ln = rng.uniform(x_a, x_b - 0.6), rng.uniform(-0.5, 0.4), rng.uniform(0.15, 0.6)
        L.append(dict(view="side", groups=fus, line=[[x, z], [x + ln, z - rng.uniform(0, 0.05)]],
                      color="#2a241c", width=rng.uniform(1.2, 3.0), alpha=rng.uniform(0.04, 0.08)))
    wg = spec["wing"]["sections"]
    half = wg[-2][1]
    for view, n, a in (("top", 16, 0.06), ("bottom", 30, 0.09)):
        for _ in range(n * level):
            y = rng.uniform(-half, half)
            t = abs(y) / half
            x = wg[0][0] + (wg[-2][0] - wg[0][0]) * t + rng.uniform(0.1, 0.6) * wg[-2][3]
            L.append(dict(view=view, groups=["wing"], line=[[x, y], [x + rng.uniform(0.2, 0.7), y]], min_dot=0.05,
                          color="#2a241c", width=rng.uniform(1.2, 3.0), alpha=rng.uniform(0.5, 1.0) * a))
    for _ in range(14 * level):
        x = rng.uniform(wg[0][0] + 0.3, wg[0][0] + wg[0][3] - 0.4)
        y = rng.choice((-1, 1)) * rng.uniform(0.45, 1.0)
        r = rng.uniform(0.015, 0.04)
        L.append(dict(view="top", groups=["wing"], min_dot=0.05, color="#b9bdc1", alpha=0.75,
                      polygon=[[x, y], [x + r * rng.uniform(1, 3), y + r * 0.4], [x + r, y + r]]))
    return L


def build_aircraft(spec: dict, p: AircraftParams) -> Model:
    s = 1000.0 / p.scale
    lv = LEVELS[int(p.level)]
    col = spec.get("colors", {})
    base = col.get("base", "#cfd3d6")
    m = Mesh()

    # --- kadłub ---------------------------------------------------------
    stations = [st for st in spec["fuselage"]["stations"] if (st[7] if len(st) > 7 else 1) <= p.level]
    n = lv["ring"]
    rings = [section(st, s, n) for st in stations]
    fus = set()
    prev = None
    spin = spec["spinner"]
    for i, (x, r) in enumerate(spin):
        ring = section((x, r, r, -r, 0.0, 2, 2), s, n) if i < len(spin) - 1 else rings[0]
        if prev is None:
            prev = [(x * s, 0.0, 0.0)] * n if r < 1e-9 else ring
            if r < 1e-9:
                continue
        part = m.add_part(f"Kołpak śmigła {len(fus) + 1}", color=col.get("spinner", "#c0392b"), smooth=True, group="spinner")
        m.loft(prev, ring, part)
        fus.add(part)
        prev = ring
    for i in range(len(rings) - 1):
        part = m.add_part(f"Kadłub – segment {i + 1}", color=base, smooth=True, group="fuselage")
        m.loft(rings[i], rings[i + 1], part)
        fus.add(part)
    tail = m.add_part("Zakończenie kadłuba", color=base, tab_priority=-1, group="fuselage")
    cap(m, rings[-1], tail)
    fus.add(tail)

    # --- płaty i kabina (jeszcze jako pełne bryły) ------------------------
    right = lambda q: q
    left = lambda q: (q[0], -q[1], q[2])
    up = lambda q: (q[0], -q[2], q[1])
    wg = spec["wing"]
    wing_r = add_surface(m, "Skrzydło prawe", "wing", wg, right, base, s, lv["wing"])
    wing_l = add_surface(m, "Skrzydło lewe", "wing", wg, left, base, s, lv["wing"])
    fin = add_surface(m, "Statecznik pionowy", "fin", spec["fin"], up, base, s, lv["tail"])
    stab_r = add_surface(m, "Statecznik poziomy prawy", "stab", spec["stab"], right, base, s, lv["tail"])
    stab_l = add_surface(m, "Statecznik poziomy lewy", "stab", spec["stab"], left, base, s, lv["tail"])
    canopy = add_canopy(m, spec["canopy"], s, lv["canopy"]) if "canopy" in spec else set()
    m.orient()

    # --- przenikania: docinamy do kadłuba (i statecznika pionowego), zostawiając obrysy ---
    solid = copy.deepcopy(m)
    face_marks = []
    stab_on = [fus, fin] if spec["stab"].get("on_fin") else [fus]
    joints = [(wing_r, [fus]), (wing_l, [fus]), (fin, [fus]), (stab_r, stab_on), (stab_l, stab_on), (canopy, [fus])]
    for k, (parts, targets) in enumerate(joints):
        for target in targets if parts else []:
            m.trim(parts, solid, target, 10000 + k)
        if parts:
            m.drop_small_parts(parts, 8.0, 10000 + k)
    for k, (parts, targets) in enumerate(joints):
        for target in targets if parts else []:
            hits = m.imprint(target, solid, parts)
            if hits:
                face_marks.append(("glue", "", 10000 + k, hits))
    marks: list[Mark] = []

    # --- szkielet (z brył przed docięciem) --------------------------------
    skin, card = p.paper, p.card
    X, Y, Z = np.eye(3)
    plates: list[Plate] = []
    if lv["skeleton"]:
        xs = wg["spar_x"] * s
        xs_form = [st[0] * s for st in stations[1:-1]]
        plates.append(plate_from_slice(solid, "K", "Kil (podłużnica)", (0, 0, 0), X, Z, skin, card, fus,
                                       clip=clip_x(xs_form[0] - 2, xs_form[-1] + 2)))
        for x in xs_form:
            if abs(x - xs) < 8.0:
                continue   # tuż obok stoi wręga z dźwigarem — dwa wpusty w kilu byłyby za blisko siebie
            k = len(plates)
            pl = plate_from_slice(solid, f"W{k}", f"Wręga {k}", (x, 0, 0), Y, Z, skin, card, fus)
            if pl:
                plates.append(pl)
        secs = wg["sections"]
        x0w, x1w = secs[0][0], secs[0][0] + secs[0][3]
        wy = max(st[1] for st in stations if x0w - 0.5 <= st[0] <= x1w + 0.5) * s
        y_ribs = list(np.linspace(wy + 2.0, secs[-2][1] * s - 1.5, lv["ribs"]))
        former = solid.slice((xs, 0, 0), X, Y, Z, fus)
        arm_sec = solid.slice((xs, 0, 0), X, Y, Z, wing_r)
        arm = largest(arm_sec.buffer(-skin, join_style="mitre")
                      .intersection(box(-1e5, -1e5, y_ribs[len(y_ribs) // 2] + 3, 1e5)))
        mirror = lambda g: affinity.scale(g, xfact=-1, origin=(0, 0))
        arms = unary_union([arm, mirror(arm)])
        poly = largest(unary_union([former.buffer(-skin, join_style="mitre"), arms]))
        limit = unary_union([former, arm_sec, mirror(arm_sec)])
        plates.append(Plate("WD", "Wręga z dźwigarem skrzydeł", np.array([xs, 0, 0.0]), Y, Z, poly, limit, card))
        for sign, parts, tag in ((1, wing_r, "P"), (-1, wing_l, "L")):
            for i, y in enumerate(y_ribs):
                pl = plate_from_slice(solid, f"Ż{i + 1}{tag}", f"Żebro {i + 1} skrzydła {'prawego' if sign > 0 else 'lewego'}",
                                      (0, sign * y, 0), X, Z, skin, card, parts)
                if pl:
                    plates.append(pl)
        # szczeliny na dźwigar: tam, gdzie płyta WD przechodzi przez poszycie kadłuba
        slots = []
        for fi, f in enumerate(m.faces):
            if f.part not in fus:
                continue
            P3 = m.face_points(fi)
            d = P3[:, 0] - xs
            cross = [P3[i] + (P3[(i + 1) % len(P3)] - P3[i]) * d[i] / (d[i] - d[(i + 1) % len(P3)])
                     for i in range(len(P3)) if (d[i] >= 0) != (d[(i + 1) % len(P3)] >= 0)]
            if len(cross) != 2:
                continue
            hit = LineString([q[1:] for q in cross]).intersection(arms)
            o, u, v, _ = m.face_frame(fi)
            lines = [np.array([[(np.array([xs, y, z]) - o) @ u, (np.array([xs, y, z]) - o) @ v] for y, z in g.coords])
                     for g in getattr(hit, "geoms", [hit]) if g.geom_type == "LineString" and g.length > 0.5]
            if lines:
                slots.append((fi, lines))
        if slots:
            face_marks.append(("cut", "wyciąć", None, slots))
        halflap(plates)

    # --- części płaskie -------------------------------------------------
    flats: list[FlatPart] = []
    if "prop" in spec:
        flats.append(add_prop(spec["prop"], s))
    if lv["gear"] and "gear" in spec:
        gf, gp = add_gear(spec["gear"], s, card)
        flats += gf
        plates += gp

    notes = []
    if plates:
        notes.append("Części szkieletu (K, W…, Ż…, koła) naklej na tekturę o grubości podanej na arkuszu "
                     "i wytnij razem z wpustami.")
    if lv["skeleton"]:
        notes += ["Złóż szkielet: wręgi W… i wręgę z dźwigarem WD wsuń we wpusty kila K.",
                  "Przed sklejeniem segmentu z czerwonym oznaczeniem „wyciąć” wytnij w nim szczeliny na dźwigar wręgi WD."]
    notes += [
        "Segmenty kadłuba zwijaj w pierścienie, sklejaj szwem od spodu i łącz kolejno; "
        "ząbki jednego segmentu wchodzą pod następny.",
        "Skrzydło: zegnij poszycie wzdłuż krawędzi natarcia" + (", wklej żebra Ż… na dźwigar" if lv["skeleton"] else "")
        + ", sklej krawędź spływu, zamknij końcówką i doklej ząbkami nasady do obrysu na kadłubie.",
        "Usterzenie i osłonę kabiny doklej ząbkami do obrysów o tym samym numerze szwu.",
    ]
    title = f"{spec['name']}" + (f" — {spec['variant']}" if spec.get("variant") else "") + f", skala 1:{p.scale:g}"
    paint = spec.get("paint", []) + auto_detail(spec, stations) + weathering(spec, stations, int(p.weather))
    return Model(title, m, plates, marks, notes, flats, layers_from_spec(paint, s), face_marks, skin, card, shading=1.0)


def load_specs() -> dict:
    out = {}
    for f in sorted(resources.files("modelarz.samoloty").iterdir(), key=lambda q: q.name):
        if f.name.endswith(".json"):
            out[f.name[:-5]] = json.loads(f.read_text(encoding="utf-8"))
    return out
