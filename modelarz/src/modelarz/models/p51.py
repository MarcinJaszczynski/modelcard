"""Samolot typu P-51 (uproszczony): kadłub jako pasy między wręgami, płaty jako powierzchnie
rozpięte między żebrem nasadowym a końcowym. Wymiary oryginału w metrach, model w mm."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union

from ..mesh import Mesh
from ..skeleton import Plate, clip_x, halflap, largest, plate_from_slice
from .base import Mark, Model, P, cap


@dataclass
class P51Params:
    scale: float = P("Skala 1:", 33, 24, 100)
    paper: float = P("Grubość kartonu poszycia [mm]", 0.25, 0.1, 0.6)
    card: float = P("Grubość tektury szkieletu [mm]", 1.0, 0.5, 2.0)
    dihedral: float = P("Wznios skrzydeł [°]", 5.0, 0, 10)


# x, połowa szerokości, góra, dół, promień naroży górnych, promień naroży dolnych  [m]
# Boki kadłuba są płaskie i równoległe w strefie skrzydła (x 2.0–4.8) oraz usterzenia
# (x 7.9–9.1) — dzięki temu płaska nasada płata przylega do kadłuba bez szczelin.
STATIONS = [
    (0.55, 0.36, 0.36, -0.36, 0.36, 0.36),
    (1.20, 0.42, 0.46, -0.52, 0.30, 0.22),
    (2.00, 0.43, 0.50, -0.64, 0.25, 0.08),
    (2.75, 0.43, 0.52, -0.68, 0.25, 0.08),
    (3.30, 0.43, 0.95, -0.70, 0.43, 0.08),
    (4.20, 0.43, 0.92, -0.74, 0.43, 0.08),
    (4.80, 0.43, 0.50, -0.74, 0.28, 0.10),
    (5.80, 0.34, 0.46, -0.58, 0.24, 0.14),
    (6.80, 0.24, 0.42, -0.28, 0.16, 0.12),
    (7.90, 0.13, 0.38, -0.05, 0.04, 0.04),
    (9.10, 0.13, 0.38, 0.10, 0.04, 0.04),
]
SPINNER = [(0.0, 0.0), (0.22, 0.22)]     # x, promień
CANOPY = (2.75, 4.80, 0.55)              # od x, do x, powyżej z
SPAR_X = 2.87
WING_ROOT = (2.10, 0.43, -0.36, 2.55, 0.15)   # x natarcia, rozpiętość, z, cięciwa, grubość względna
WING_TIP = (2.55, 5.64, -0.36, 1.30, 0.11)
STAB_ROOT = (7.95, 0.13, 0.21, 1.10, 0.10)
STAB_TIP = (8.30, 2.00, 0.21, 0.60, 0.09)
FIN_ROOT = (7.95, 0.38, 0.0, 1.13, 0.09)
FIN_TIP = (8.65, 1.80, 0.0, 0.65, 0.08)

ALU, GLASS, RED, DARK = "#cfd3d6", "#a9cfe8", "#c0392b", "#8a9299"


def section(st, s, arc=4):
    x, w, zt, zb, rt, rb = st
    pts = [(0.0, zb)]
    for i in range(arc + 1):
        a = -math.pi / 2 + math.pi / 2 * i / arc
        pts.append((w - rb + rb * math.cos(a), zb + rb + rb * math.sin(a)))
    pts.append((w, (zb + rb + zt - rt) / 2))
    for i in range(arc + 1):
        a = math.pi / 2 * i / arc
        pts.append((w - rt + rt * math.cos(a), zt - rt + rt * math.sin(a)))
    pts.append((0.0, zt))
    pts += [(-y, z) for y, z in reversed(pts[1:-1])]
    return [(x * s, y * s, z * s) for y, z in pts]


def naca(m, t, camber):
    """Obrys profilu o cięciwie 1: spływ -> góra -> natarcie -> dół."""
    xs = [(1 - math.cos(math.pi * i / m)) / 2 for i in range(m + 1)]
    yt = lambda x: 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x**2 + 0.2843 * x**3 - 0.1036 * x**4)
    p = 0.4
    yc = lambda x: camber / p**2 * (2 * p * x - x * x) if x < p else camber / (1 - p)**2 * (1 - 2 * p + 2 * p * x - x * x)
    return [(x, yc(x) + yt(x)) for x in reversed(xs)] + [(x, yc(x) - yt(x)) for x in xs[1:-1]]


def add_surface(m: Mesh, name, root, tip, xf, color, tip_color, camber, s, normal, marks, pts=10):
    def ring(d):
        xle, y, zc, chord, t = d
        return [xf(((xle + chord * x) * s, y * s, (zc + chord * z) * s)) for x, z in naca(pts, t, camber)]
    R, T = ring(root), ring(tip)
    skin = m.add_part(name, color=color, smooth=True, tab_priority=1)
    tipp = m.add_part(f"{name} – końcówka", color=tip_color, tab_priority=-1)
    rootp = m.add_part(f"{name} – nasada", virtual=True)
    m.loft(R, T, skin, cut_at=0)
    cap(m, T, tipp)
    cap(m, R, rootp)
    marks.append(Mark(R, True, "glue", "", normal=normal, seam_of=rootp))
    return {skin, tipp, rootp}


def build_p51(p: P51Params) -> Model:
    s = 1000.0 / p.scale
    m = Mesh()
    marks: list[Mark] = []

    # --- kadłub ---------------------------------------------------------
    rings = [section(st, s) for st in STATIONS]
    n = len(rings[0])
    fus = set()
    prev = [(0.0, 0.0, 0.0)] * n
    for i, st in enumerate(SPINNER[1:] + [None]):
        ring = rings[0] if st is None else section((st[0], st[1], st[1], -st[1], st[1], st[1]), s)
        part = m.add_part("Kołpak śmigła – czubek" if i == 0 else "Kołpak śmigła", color=RED, smooth=True)
        m.loft(prev, ring, part)
        fus.add(part)
        prev = ring
    for i in range(len(rings) - 1):
        part = m.add_part(f"Kadłub – segment {i + 1}", color=ALU, smooth=True)
        m.loft(rings[i], rings[i + 1], part)
        fus.add(part)
        x0, x1 = STATIONS[i][0], STATIONS[i + 1][0]
        if x0 >= CANOPY[0] and x1 <= CANOPY[1]:
            for fi, f in enumerate(m.faces):
                if f.part == part and m.face_points(fi)[:, 2].mean() > CANOPY[2] * s:
                    f.color = GLASS
    tail = m.add_part("Zakończenie kadłuba", color=DARK, tab_priority=-1)
    cap(m, rings[-1], tail)
    fus.add(tail)

    # --- płaty ----------------------------------------------------------
    dz = (WING_TIP[1] - WING_ROOT[1]) * math.tan(math.radians(p.dihedral))
    wtip = (WING_TIP[0], WING_TIP[1], WING_TIP[2] + dz, WING_TIP[3], WING_TIP[4])
    right = lambda q: q
    left = lambda q: (q[0], -q[1], q[2])
    up = lambda q: (q[0], -q[2], q[1])
    wing_r = add_surface(m, "Skrzydło prawe", WING_ROOT, wtip, right, ALU, RED, 0.02, s, (0, 1, 0), marks)
    wing_l = add_surface(m, "Skrzydło lewe", WING_ROOT, wtip, left, ALU, RED, 0.02, s, (0, -1, 0), marks)
    add_surface(m, "Statecznik poziomy prawy", STAB_ROOT, STAB_TIP, right, ALU, ALU, 0.0, s, (0, 1, 0), marks, 8)
    add_surface(m, "Statecznik poziomy lewy", STAB_ROOT, STAB_TIP, left, ALU, ALU, 0.0, s, (0, -1, 0), marks, 8)
    add_surface(m, "Statecznik pionowy", FIN_ROOT, FIN_TIP, up, ALU, RED, 0.0, s, (0, 0, 1), marks, 8)
    m.orient()

    # --- szkielet -------------------------------------------------------
    skin, card = p.paper, p.card
    X, Y, Z = np.eye(3)
    plates: list[Plate] = []
    xs_form = [st[0] * s for st in STATIONS[1:-1]]
    keel = plate_from_slice(m, "K", "Kil (podłużnica)", (0, 0, 0), X, Z, skin, card, fus,
                            clip=clip_x(xs_form[0] - 2, xs_form[-1] + 2))
    plates.append(keel)
    for i, x in enumerate(xs_form):
        if abs(x - SPAR_X * s) < 8.0:
            continue   # tuż obok stoi wręga z dźwigarem — dwa wpusty w kilu byłyby za blisko siebie
        k = len(plates)
        pl = plate_from_slice(m, f"W{k}", f"Wręga {k}", (x, 0, 0), Y, Z, skin, card, fus)
        if pl:
            plates.append(pl)

    xs = SPAR_X * s
    wy = WING_ROOT[1] * s
    y_ribs = [wy + 1.5, (wy + wtip[1] * s) / 2, wtip[1] * s - 1.5]
    former = m.slice((xs, 0, 0), X, Y, Z, fus)
    arm_sec = m.slice((xs, 0, 0), X, Y, Z, wing_r)
    arm = largest(arm_sec.buffer(-skin, join_style="mitre").intersection(box(-1e5, -1e5, y_ribs[1] + 3, 1e5)))
    zb = arm.intersection(box(wy + 0.5, -1e5, wy + 2.5, 1e5)).bounds
    zlo, zhi = zb[1] + 0.3, zb[3] - 0.3
    bridge = box(wy - 2.0, zlo, wy + 2.0, zhi)
    half = unary_union([arm, bridge])
    mirror = lambda g: affinity.scale(g, xfact=-1, origin=(0, 0))
    poly = largest(unary_union([former.buffer(-skin, join_style="mitre"), half, mirror(half)]))
    limit = unary_union([former, arm_sec, mirror(arm_sec), bridge, mirror(bridge)])
    plates.append(Plate("WD", "Wręga z dźwigarem skrzydeł", np.array([xs, 0, 0.0]), Y, Z, poly, limit, card))
    for sign, parts, tag in ((1, wing_r, "P"), (-1, wing_l, "L")):
        for i, y in enumerate(y_ribs):
            pl = plate_from_slice(m, f"Ż{i + 1}{tag}", f"Żebro {i + 1} skrzydła {'prawego' if sign > 0 else 'lewego'}",
                                  (0, sign * y, 0), X, Z, skin, card, parts)
            if pl:
                plates.append(pl)
        x0, x1 = xs - card / 2 - 0.1, xs + card / 2 + 0.1
        yy = sign * wy
        marks.append(Mark([(x0, yy, zlo), (x1, yy, zlo), (x1, yy, zhi), (x0, yy, zhi)], True, "cut",
                          "wyciąć", normal=(0, sign, 0)))
    halflap(plates)

    notes = [
        "Części szkieletu (K, W…, Ż…) naklej na tekturę o grubości podanej na arkuszu i wytnij razem z wpustami.",
        "Złóż szkielet: wręgi W… i wręgę z dźwigarem WD wsuń we wpusty kila K.",
        "Segmenty kadłuba zwijaj w pierścienie, sklejaj szwem od spodu i nasuwaj kolejno na wręgi; "
        "ząbki jednego segmentu wchodzą pod następny.",
        "Przed sklejeniem segmentu z czerwonym oznaczeniem „wyciąć” wytnij w nim szczeliny na dźwigar wręgi WD.",
        "Skrzydło: zegnij poszycie wzdłuż krawędzi natarcia, wklej żebra Ż… na dźwigar, sklej krawędź spływu, "
        "zamknij końcówką i doklej ząbkami nasady do obrysu na kadłubie.",
        "Usterzenie doklej ząbkami do obrysów na ogonie kadłuba.",
    ]
    return Model(f"Samolot typu P-51 (uproszczony), skala 1:{p.scale:g}", m, plates, marks, notes, skin, card)
