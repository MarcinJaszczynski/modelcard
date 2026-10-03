"""Model złożony z prostych brył opisanych w danych: graniastosłupy (także o pochyłych ścianach),
bryły obrotowe, kadłub okrętu z wręg, koła, gąsienice, rurki zwijane na drucie i druty.
Na tym stoją czołgi, okręty i pojazdy. Wymiary oryginału w metrach, model w mm.

Bryła może stać na innej: ściana styku jest wtedy niedrukowana, krawędzie wokół niej dostają
zakładki, a na ścianie pod spodem pojawia się obrys przyklejenia z numerem szwu."""
from __future__ import annotations

import math

import numpy as np
from shapely.geometry import Point, box

from ..mesh import Mesh
from ..paint import layers_from_spec
from ..skeleton import Plate, clip_x, halflap, plate_from_slice
from .base import FlatPart, Mark, Model, cap

AX = {"x": lambda a, b, c: (c, a, b), "y": lambda a, b, c: (a, c, b), "z": lambda a, b, c: (a, b, c)}
DIR = {"x": np.array([1.0, 0, 0]), "y": np.array([0, 1.0, 0]), "z": np.array([0, 0, 1.0])}


def _hidden(m: Mesh, ring, name, normal, marks):
    part = m.add_part(f"{name} – styk", virtual=True)
    cap(m, ring, part)
    marks.append(Mark(ring, True, "glue", "", normal=tuple(normal), seam_of=part))


def add_prism(m: Mesh, d: dict, s: float, marks: list, sign: float = 1.0):
    """Graniastosłup: wielokąt `profile` wyciągnięty wzdłuż osi; `top_scale` zwęża górę (ściany pochyłe)."""
    ax, f = d["axis"], AX[d["axis"]]
    prof = [(a * s, b * s) for a, b in d["profile"]]
    c0, c1 = d["from"] * s, d["to"] * s
    k = d.get("top_scale", 1.0)
    ca, cb = sum(a for a, _ in prof) / len(prof), sum(b for _, b in prof) / len(prof)
    flip = (lambda q: (q[0], -q[1], q[2])) if sign < 0 else (lambda q: q)
    A = [flip(f(a, b, c0)) for a, b in prof]
    B = [flip(f(ca + (a - ca) * k, cb + (b - cb) * k, c1)) for a, b in prof]
    name = d["name"] + (" (lewa)" if sign < 0 else "")
    kw = dict(color=d.get("color", "#9aa0a6"), group=d.get("group", ""), smooth=d.get("smooth", False),
              tab_priority=d.get("priority", 0))
    hidden = d.get("hidden", [])
    side = m.add_part(name, **kw)
    ends = side if len(prof) <= 4 and not kw["smooth"] else None   # proste pudło rozwijamy w jednym kawałku
    hid = {}
    for e in hidden:
        if isinstance(e, int):
            hid[e] = m.add_part(f"{name} – styk {e}", virtual=True)
    m.loft(A, B, lambda i: hid.get(i, side), cut_at=None if ends is not None else 0)
    for e, part in hid.items():
        n = len(A)
        quad = [A[e], A[(e + 1) % n], B[(e + 1) % n], B[e]]
        p = [np.asarray(q, float) for q in quad]
        nrm = np.cross(p[1] - p[0], p[3] - p[0])
        cen = (np.mean([np.asarray(q) for q in A], axis=0) + np.mean([np.asarray(q) for q in B], axis=0)) / 2
        if nrm @ (p[0] - cen) < 0:
            nrm = -nrm
        marks.append(Mark(quad, True, "glue", "", normal=tuple(-nrm / np.linalg.norm(nrm)), seam_of=part))
    axis = DIR[ax] * (1 if ax != "y" else sign)
    for ring, tag, nrm in ((A, "from", axis), (B, "to", -axis)):
        if tag in hidden:
            _hidden(m, ring, f"{name} {tag}", nrm, marks)
        else:
            part = ends if ends is not None else m.add_part(f"{name} – ściana", **{**kw, "smooth": False, "tab_priority": -1})
            cap(m, ring, part)


def add_frustum(m: Mesh, d: dict, s: float, marks: list, sign: float = 1.0):
    ax, f = d["axis"], AX[d["axis"]]
    a0, b0 = d["at"]
    r1 = d["r"] if isinstance(d["r"], list) else [d["r"], d["r"]]
    r2 = d.get("r2", r1)
    r2 = r2 if isinstance(r2, list) else [r2, r2]
    n = d.get("n", 16)
    flip = (lambda q: (q[0], -q[1], q[2])) if sign < 0 else (lambda q: q)
    ring = lambda r, c: [flip(f((a0 + r[0] * math.cos(2 * math.pi * i / n)) * s,
                                (b0 + r[1] * math.sin(2 * math.pi * i / n)) * s, c * s)) for i in range(n)]
    A, B = ring(r1, d["from"]), ring(r2, d["to"])
    name = d["name"] + (" (lewa)" if sign < 0 else "")
    kw = dict(color=d.get("color", "#9aa0a6"), group=d.get("group", ""))
    side = m.add_part(name, smooth=True, tab_priority=1, **kw)
    m.loft(A, B, side)
    hidden = d.get("hidden", [])
    axis = DIR[ax] * (1 if ax != "y" else sign)
    for ring_, tag, nrm in ((A, "from", axis), (B, "to", -axis)):
        if max(r1 if tag == "from" else r2) < 1e-9:
            continue
        if tag in hidden:
            _hidden(m, ring_, f"{name} {tag}", nrm, marks)
        else:
            cap(m, ring_, m.add_part(f"{name} – denko", tab_priority=-1, **kw))


def add_hull(m: Mesh, d: dict, s: float) -> set:
    """Kadłub okrętu z wręg: [x, połowa szerokości pokładu, połowa szerokości dna, pokład z, dno z]."""
    kw = dict(group=d.get("group", "hull"))
    deck = m.add_part("Pokład", color=d.get("deck_color", "#8a6f4d"), **kw)
    right = m.add_part("Burta prawa", color=d.get("color", "#7d8790"), smooth=True, tab_priority=1, **kw)
    left = m.add_part("Burta lewa", color=d.get("color", "#7d8790"), smooth=True, tab_priority=1, **kw)
    bottom = m.add_part("Dno", color=d.get("bottom_color", "#7a2e24"), **kw)
    pick = [right, bottom, left, deck]
    rings = [[(x * s, bd * s, zd * s), (x * s, bw * s, zb * s), (x * s, -bw * s, zb * s), (x * s, -bd * s, zd * s)]
             for x, bd, bw, zd, zb in d["stations"]]
    for A, B in zip(rings, rings[1:]):
        m.loft(A, B, lambda k: pick[k], cut_at=None)
    for ring, label in ((rings[0], "Dziób"), (rings[-1], "Pawęż")):
        cap(m, ring, m.add_part(label, color=d.get("color", "#7d8790"), tab_priority=-1, **kw))
    return {deck, right, left, bottom} | {i for i, p in enumerate(m.parts) if p.name in ("Dziób", "Pawęż")}


def add_shell(m: Mesh, d: dict, s: float):
    """Skorupa z pasów podłużnych rozpiętych na przekrojach (nadwozie samochodu, kadłub łodzi):
    każdy bok przekroju to osobna część biegnąca przez całą długość, np. bok, okna, maska–szyby–dach."""
    parts = [m.add_part(e["name"], color=e.get("color", d.get("color", "#9aa0a6")), group=e.get("group", ""),
                        smooth=e.get("smooth", True), tab_priority=e.get("priority", 0)) for e in d["edges"]]
    rings = [[(x * s, y * s, z * s) for y, z in ring] for x, ring in d["stations"]]
    for A, B in zip(rings, rings[1:]):
        m.loft(A, B, lambda k: parts[k], cut_at=None)
    for ring, e in ((rings[0], d["caps"][0]), (rings[-1], d["caps"][1])):
        cap(m, ring, m.add_part(e["name"], color=e.get("color", d.get("color", "#9aa0a6")), group=e.get("group", ""),
                                tab_priority=-1))


def add_tube(d: dict, s: float, wires: list) -> FlatPart:
    a, b = np.array(d["from"], float) * s, np.array(d["to"], float) * s
    L, dia = float(np.linalg.norm(b - a)), d["d"] * s
    u = (b - a) / L
    v = np.cross(u, [0, 0, 1.0])
    v = v / np.linalg.norm(v) if np.linalg.norm(v) > 1e-9 else np.array([0, 1.0, 0])
    w = math.pi * dia + 2.0
    wire = max(0.5, round((dia - 0.6) * 2) / 2)
    wires.append((f"{d['name']} – rdzeń", L, wire, a, b))
    return FlatPart(d["name"], box(0, 0, L, w), box(0, -dia / 2, L, dia / 2), d.get("color", "#6b6f72"),
                    [(a, u, v)], [((0, w - 2.0), (L, w - 2.0))], [],
                    f"wytnij, zwiń ciasno w rurkę na drucie {wire:g} mm i sklej zakładką")


def add_wheels(d: dict, s: float, card: float, plates: list, flats: list, count: list):
    r, width = d["r"] * s, d["width"] * s
    X, Y, Z = np.eye(3)
    disc = Point(0, 0).buffer(r, 24)
    layers = max(1, min(3, round(width / 2 / card)))
    faces, rims = [], []
    for cx, cy, cz in d["centers"]:
        for sign in (1, -1):
            c = np.array([cx * s, sign * cy * s, cz * s])
            for k in range(layers):
                count[0] += 1
                plates.append(Plate(f"K{count[0]}", f"{d['name']} – rdzeń", c + Y * sign * (k - layers / 2) * card,
                                    X, Z, disc, disc, card))
            faces += [(c + Y * width / 2, X, Z), (c - Y * width / 2, X, Z)]
            rims.append((c - Y * width / 2 + X * r, Y, Z * 0))
    flats.append(FlatPart(f"{d['name']} – tarcza", disc, disc, d.get("color", "#3d4a30"), faces, [],
                          [(Point(0, 0).buffer(r * 0.35, 20), d.get("hub_color", "#2a2a2a"))],
                          f"wytnij i naklej z obu stron na rdzeń z {layers} warstw tektury"))
    strip = box(0, 0, 2 * math.pi * r + 2, width)
    flats.append(FlatPart(f"{d['name']} – bieżnik", strip, box(0, 0, 0.01, 0.01), d.get("rim_color", "#1e1e1e"),
                          [f for f in rims], [], [], "wytnij i oklej obwód koła"))


def add_track(d: dict, s: float, flats: list):
    x0, x1, r, width = d["x"][0] * s, d["x"][1] * s, d["r"] * s, d["width"] * s
    total = 2 * (x1 - x0) + 2 * math.pi * r
    n = max(1, math.ceil(total / 170.0))
    L = total / n
    pitch = max(3.0, d.get("pitch", 0.17) * s)
    folds = [((k * pitch, 0), (k * pitch, width)) for k in range(1, int(L / pitch) + 1) if k * pitch < L - 0.5]
    frames = [(np.array([x0, sign * d["y"] * s - width / 2, (d["z"] - d["r"]) * s]), np.array([1.0, 0, 0]), np.array([0, 1.0, 0]))
              for sign in (1, -1)] * n
    flats.append(FlatPart(d["name"], box(0, 0, L, width), box(0, 0, min(L, x1 - x0), width), d.get("color", "#2b2b2b"),
                          frames, folds, [], f"wytnij {2 * n} odcinków, połącz po {n} w taśmę i opasaj koła"))


def build_scene(spec: dict, p) -> Model:
    s = 1000.0 / p.scale
    m = Mesh()
    marks: list[Mark] = []
    hull_parts: set = set()
    hull = None
    for d in spec.get("solids", []):
        for sign in ((1.0, -1.0) if d.get("mirror") else (1.0,)):
            if d["type"] == "prism":
                add_prism(m, d, s, marks, sign)
            elif d["type"] == "box":
                x, y, z = d["at"]
                l, w, h = d["size"]
                add_prism(m, {**d, "axis": "z", "from": z, "to": z + h,
                              "profile": [[x, y], [x + l, y], [x + l, y + w], [x, y + w]]}, s, marks, sign)
            elif d["type"] == "frustum":
                add_frustum(m, d, s, marks, sign)
            elif d["type"] == "shell":
                add_shell(m, d, s)
            elif d["type"] == "hull":
                hull, hull_parts = d, add_hull(m, d, s)
            else:
                raise ValueError(f"nieznany typ bryły: {d['type']}")
    m.orient()

    plates: list[Plate] = []
    flats: list[FlatPart] = []
    wires: list = []
    X, Y, Z = np.eye(3)
    if hull is not None:   # szkielet okrętu: kil i wręgi z tej samej bryły
        xs = [st[0] * s for st in hull["stations"]]
        keel = plate_from_slice(m, "K", "Kil", (0, 0, 0), X, Z, p.paper, p.card, hull_parts,
                                clip=clip_x(xs[0] + 3, xs[-1] - 1))
        if keel:
            plates.append(keel)
        for x in xs[1:-1]:
            pl = plate_from_slice(m, f"W{len(plates)}", f"Wręga {len(plates)}", (x, 0, 0), Y, Z, p.paper, p.card, hull_parts)
            if pl:
                plates.append(pl)
        halflap(plates)
    count = [0]
    for d in spec.get("wheels", []):
        add_wheels(d, s, p.card, plates, flats, count)
    for d in spec.get("tracks", []):
        add_track(d, s, flats)
    for d in spec.get("tubes", []):
        flats.append(add_tube(d, s, wires))
    for d in spec.get("wires", []):
        a, b = np.array(d["from"], float) * s, np.array(d["to"], float) * s
        wires.append((d["name"], float(np.linalg.norm(b - a)), d.get("d", 0.5), a, b))

    notes = list(spec.get("notes", []))
    if plates:
        notes.insert(0, "Części szkieletu i rdzenie kół naklej na tekturę o grubości podanej na arkuszu.")
    notes.append("Duże płaskie ściany warto podkleić od środka tekturą 0,5–1 mm, żeby się nie zapadały.")
    title = spec["name"] + (f" — {spec['variant']}" if spec.get("variant") else "") + f", skala 1:{p.scale:g}"
    return Model(title, m, plates, marks, notes, flats, layers_from_spec(spec.get("paint", []), s), [],
                 p.paper, p.card, shading=1.0, wires=wires)
