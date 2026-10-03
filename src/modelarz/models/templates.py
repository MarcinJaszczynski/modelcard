"""Szablony kategorii: z kilkunastu faktów o pojeździe (wymiary, kolory, napisy) powstaje pełny
opis sceny z brył. Tyle potrafi podać wyszukiwarka i model językowy — resztę wie szablon.
Układ: x od przodu do tyłu, y w bok, z w górę od ziemi; metry."""
from __future__ import annotations

import math

from ..paint import panel_line, rivet_line

GLASS = "#9fc3dc"


def _oct(cx, l, w, cut=0.28):
    a, b, c = l / 2, w / 2, cut
    return [[cx - a, -b * (1 - c)], [cx - a * (1 - c), -b], [cx + a * (1 - c), -b], [cx + a, -b * (1 - c)],
            [cx + a, b * (1 - c)], [cx + a * (1 - c), b], [cx - a * (1 - c), b], [cx - a, b * (1 - c)]]


def tank(f: dict, level: int = 2, **_) -> dict:
    L, W, H, g = f["dlugosc_kadluba"], f["szerokosc"], f["wysokosc_kadluba"], f.get("przeswit", 0.4)
    tw = f.get("szerokosc_gasienicy", 0.5)
    col = f.get("kolor", "#4b5a3a")
    hs = g + 0.5 * (H - g)                       # wysokość półek nad gąsienicami
    t = f["wieza"]
    tx, tl, tww, th = t["x"], t["dlugosc"], t["szerokosc"], t["wysokosc"]
    wheels = f["kola"]
    r, n = wheels["promien"], wheels["liczba"]
    yw = W / 2 - tw / 2
    solids = [
        {"type": "prism", "name": "Wanna kadłuba", "axis": "y", "group": "hull", "color": col,
         "from": -(W / 2 - tw - 0.04), "to": W / 2 - tw - 0.04, "hidden": [2],
         "profile": [[0.06 * L, g], [0.95 * L, g], [0.985 * L, hs], [0.0, hs]]},
        {"type": "prism", "name": "Kadłub górny", "axis": "y", "group": "hull", "color": col,
         "from": -W / 2 * 0.98, "to": W / 2 * 0.98,
         "profile": [[0.0, hs], [L, hs], [L, hs + 0.1 * (H - hs)], [0.87 * L, H], [0.21 * L, H]]},
        {"type": "prism", "name": "Wieża", "axis": "z", "group": "turret", "color": col, "from": H, "to": H + th,
         "top_scale": 0.84, "hidden": ["from"], "profile": _oct(tx, tl, tww)},
    ]
    if level >= 2:
        solids.append({"type": "frustum", "name": "Wieżyczka dowódcy", "axis": "z", "group": "turret", "color": col,
                       "at": [tx + 0.12 * tl, 0.16 * tww], "r": 0.14 * tww * 1.6, "from": H + th, "to": H + th + 0.2,
                       "n": 12, "hidden": ["from"]})
    lufa = f["lufa"]
    zg = H + 0.5 * th
    centers = [[0.16 * L + i * (0.64 * L) / (n - 1), yw, r] for i in range(n)]
    spec = {
        "name": f["nazwa"], "variant": f.get("wariant", ""), "solids": solids,
        "tubes": [{"name": "Lufa", "d": max(lufa["kaliber"] * 1.5, 0.09), "color": col,
                   "from": [tx - tl / 2, 0, zg], "to": [tx - tl / 2 - lufa["dlugosc"], 0, zg]}],
        "wheels": [{"name": "Koło nośne", "r": r, "width": 0.3, "centers": centers, "color": col},
                   {"name": "Koło napinające i napędowe", "r": r * 0.62, "width": 0.3, "color": col,
                    "centers": [[0.045 * L, yw, hs - 0.22], [0.945 * L, yw, hs - 0.22]]}],
        "tracks": [{"name": "Gąsienica", "x": [0.045 * L, 0.945 * L], "r": r * 0.8, "z": r, "y": yw, "width": tw}],
        "paint": [], "notes": ["Lufę zwiń na drucie i wklej w przód wieży; koła sklej z warstw tektury i oklej tarczami.",
                               "Gąsienice opasz wokół kół po sklejeniu kadłuba."],
    }
    P = spec["paint"]
    for x in (0.3 * L, 0.55 * L, 0.8 * L):   # płyty pancerza i włazy
        P += panel_line("side", [[x, hs], [x, H]], ["hull"])
    P += panel_line("top", [[0.25 * L, -0.3 * W], [0.25 * L, 0.3 * W]], ["hull"])
    P += panel_line("top", [[0.72 * L, -0.45 * W], [0.72 * L, 0.45 * W]], ["hull"])
    P += rivet_line("side", [[0.02 * L, hs + 0.04], [0.98 * L, hs + 0.04]], ["hull"])
    P += [{"view": "top", "rect": [0.75 * L, -0.3 * W, 0.84 * L, 0.3 * W], "color": "#1c1c1c", "alpha": 0.55, "groups": ["hull"]}]
    for i in range(6 * max(1, level)):       # zacieki i kurz
        x = 0.05 * L + (i * 0.618 % 1) * 0.9 * L
        P.append({"view": "side", "groups": ["hull", "turret"], "line": [[x, H * 0.98], [x + 0.02, hs + 0.05]],
                  "color": "#2a241c", "width": 2.2, "alpha": 0.07})
    P.append({"view": "side", "rect": [0, hs, L, hs + 0.12], "color": "#6b5a3c", "alpha": 0.18, "groups": ["hull"]})
    for nap in f.get("napisy", []):
        on_turret = nap.get("miejsce", "wieza") == "wieza"
        P.append({"view": "side", "text": nap["tekst"], "size": nap.get("wysokosc", 0.3),
                  "at": [tx + nap.get("dx", 0.0), (H + th * 0.5) if on_turret else (hs + (H - hs) * 0.55)],
                  "color": nap.get("kolor", "#f4f4f0"), "groups": ["turret" if on_turret else "hull"]})
    return spec


BODIES = {   # początek i koniec kabiny, pochylenie szyby przedniej i tylnej — w ułamkach długości
    "fastback": (0.27, 0.90, 0.12, 0.16),
    "hatchback": (0.27, 0.93, 0.11, 0.09),
    "sedan": (0.28, 0.78, 0.10, 0.10),
    "kombi": (0.27, 0.97, 0.10, 0.03),
}


def _interp(pts, x):
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            t = (x - xs[i - 1]) / max(xs[i] - xs[i - 1], 1e-9)
            return ys[i - 1] + t * (ys[i] - ys[i - 1])
    return ys[-1]


def car_shell(f: dict, level: int = 2) -> dict:
    """Samochód z rzutów odczytanych z planu: sylwetka boczna, obrys z góry i zwężenie kabiny z rzutu z przodu.
    Nadwozie to pasy podłużne (boki, okna, maska–szyby–dach, podłoga) rozpięte na przekrojach."""
    from shapely.geometry import Polygon, box
    L, W, H = f["dlugosc"], f["szerokosc"], f["wysokosc"]
    wb, r = f["rozstaw_osi"], f["promien_kola"]
    col, g = f.get("kolor", "#c8452c"), f.get("przeswit", 0.16)
    env = [list(q) for q in f["profil_gora"]]
    if f.get("odwroc_profil"):
        env = [[L - x, z] for x, z in reversed(env)]
    hood = sorted(z for x, z in env if 0.06 * L <= x <= 0.2 * L)
    zb = min(0.8 * H, 1.03 * hood[len(hood) // 2]) if hood else 0.62 * H
    top = f.get("obrys_gora")
    if top and f.get("odwroc_profil"):
        top = [[L - x, w] for x, w in reversed(top)]

    def half(x):          # połowa szerokości z rzutu z góry, wygładzona; bez planu — lekko zwężone końce
        if top:
            at = lambda q: min(_interp(top, min(max(q, 0), L)), W / 2)
            vals = [at(x + d * L) for d in (-0.06, -0.03, 0, 0.03, 0.06)]
            w = sum(vals) / len(vals)
            if 0.18 * L < x < 0.82 * L:   # proste boki bywają na skanie wycięte razem z liniami wymiarowymi
                w = max(w, max(at(x + d * L) for d in (-0.16, -0.08, 0.08, 0.16)))
            return max(w, 0.3 * W)
        return W / 2 * (1 - 0.14 * abs(2 * x / L - 1) ** 3)
    front = f.get("obrys_przod")
    roof = 0.74
    if front:
        hi = [w for z, w in front if z >= 0.9 * H]
        if hi and max(w for _, w in front) > 0:
            roof = min(0.9, max(0.55, max(hi) / max(w for _, w in front)))
    n = 10 + 3 * level
    xs = sorted({round(x, 4) for x, _ in env} | {round(L * i / n, 4) for i in range(n + 1)})
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 0.012 * L]
    stations = []
    for x in xs:
        zt = max(_interp(env, x), g + 0.12)
        w = half(x)
        zbelt = min(zb, zt)
        t = max(0.0, (zt - zb) / max(H - zb, 1e-9))
        wr = w * (1 - (1 - roof) * min(1.0, t * 1.6))
        wl = w - 0.035
        stations.append([x, [[wl, g], [w, zbelt], [wr, zt], [-wr, zt], [-w, zbelt], [-wl, g]]])
    shell = {"type": "shell", "color": col, "stations": stations,
             "edges": [{"name": "Bok prawy", "group": "body"}, {"name": "Okna prawe", "group": "cabin"},
                       {"name": "Maska, szyby i dach", "group": "top"}, {"name": "Okna lewe", "group": "cabin"},
                       {"name": "Bok lewy", "group": "body"}, {"name": "Podłoga", "group": "floor", "color": "#3a3a3a"}],
             "caps": [{"name": "Przód", "group": "body"}, {"name": "Tył", "group": "body"}]}
    fo = (L - wb) * 0.47
    axles = [fo, fo + wb]
    P = []
    for x in axles:
        arc = [[x + 1.18 * r * math.cos(math.pi * k / 12), r + 1.18 * r * math.sin(math.pi * k / 12)] for k in range(13)]
        P.append({"view": "side", "polygon": [[x + 1.18 * r, g]] + arc + [[x - 1.18 * r, g]], "color": "#141414", "groups": ["body"]})
    full = Polygon(env + [[L - 0.03 * L, g], [0.03 * L, g]]).buffer(0)
    cab = full.intersection(box(-1, zb, L + 1, H + 1))
    cab = max(getattr(cab, "geoms", [cab]), key=lambda q: q.area)
    glass = cab.buffer(-0.055)
    mid = glass.centroid.x if not glass.is_empty else L / 2
    panes = glass.difference(box(mid - 0.025, 0, mid + 0.025, H + 1))
    for pane in getattr(panes, "geoms", [panes]):
        if pane.geom_type == "Polygon" and pane.area > 0.01:
            P.append({"view": "side", "polygon": [list(q) for q in pane.simplify(0.01).exterior.coords[:-1]],
                      "color": GLASS, "groups": ["cabin"], "min_dot": 0.2})
    cw = half(mid) * 0.9
    for view in ("front", "back"):
        P.append({"view": view, "rect": [-cw, zb + 0.05, cw, H - 0.07], "color": GLASS, "groups": ["top"], "min_dot": 0.3})
        P.append({"view": view, "rect": [-0.47 * W, g + 0.14, 0.47 * W, g + 0.22], "color": "#c9ccd0", "groups": ["body"], "min_dot": 0.2})
    zl = g + 0.62 * (zb - g)
    for sy in (-1, 1):
        P.append({"view": "front", "polygon": [[sy * 0.31 * W + 0.075 * math.cos(a / 8 * math.pi), zl + 0.075 * math.sin(a / 8 * math.pi)]
                                               for a in range(16)], "color": "#f1ecd2", "groups": ["body"], "min_dot": 0.2})
        a, b = sorted([sy * 0.38 * W, sy * 0.26 * W])
        P.append({"view": "back", "rect": [a, zl - 0.05, b, zl + 0.05], "color": "#b3261e", "groups": ["body"], "min_dot": 0.2})
    P += panel_line("side", [[mid, g + 0.12], [mid, zb]], ["body"])
    xw = min(x for x, _ in cab.exterior.coords)
    P += panel_line("side", [[xw + 0.02 * L, g + 0.12], [xw + 0.02 * L, zb]], ["body"])
    P += panel_line("side", [[0.02 * L, zb - 0.12], [0.98 * L, zb - 0.12]], ["body"])
    P += panel_line("top", [[xw - 0.03, -0.4 * W], [xw - 0.03, 0.4 * W]], ["top"])
    P.append({"view": "side", "rect": [0, g, L, g + 0.10], "color": "#3a3026", "alpha": 0.22, "groups": ["body"]})
    return {"name": f["nazwa"], "variant": f.get("wariant", ""), "solids": [shell],
            "wheels": [{"name": "Koło", "r": r, "width": 0.14, "centers": [[x, half(x) - 0.09, r] for x in axles],
                        "color": "#c9ccd0", "hub_color": "#8d9399"}],
            "paint": P, "notes": ["Boki, pas maska–szyby–dach i podłogę uformuj zgodnie z krzywizną i sklej szwami wzdłuż krawędzi.",
                                  "Koła sklej z warstw tektury, oklej tarczami i bieżnikiem, przyklej we wnękach."]}


def car(f: dict, level: int = 2, wnetrze: int = 0, **_) -> dict:
    if f.get("profil_gora") and not wnetrze:
        return car_shell(f, level)
    L, W, H = f["dlugosc"], f["szerokosc"], f["wysokosc"]
    wb, r = f["rozstaw_osi"], f["promien_kola"]
    col = f.get("kolor", "#c8452c")
    g = f.get("przeswit", 0.16)
    zb = f.get("linia_okien", 0.62 * H)
    ws, re, sw, sr = (k * L for k in BODIES[f.get("nadwozie", "hatchback")])
    hw = 0.43 * W
    body_prof = [[0.0, g + 0.16], [0.015 * L, zb - 0.10], [ws, zb], [re, zb], [L - 0.005 * L, zb - 0.10],
                 [L, g + 0.18], [L - 0.05 * L, g], [0.05 * L, g]]
    cab_prof, cab_hidden = [[ws, zb], [re, zb], [re - sr, H], [ws + sw, H]], 0
    glass_side = None
    if f.get("profil_gora"):     # sylwetka odczytana z planu zamiast kształtu z szablonu
        from shapely.geometry import Polygon, box
        env = [list(q) for q in f["profil_gora"]]
        if f.get("odwroc_profil"):
            env = [[L - x, z] for x, z in reversed(env)]
        hood = sorted(z for x, z in env if 0.06 * L <= x <= 0.2 * L)
        zb = min(0.8 * H, 1.03 * hood[len(hood) // 2]) if hood else zb
        full = Polygon(env + [[L - 0.03 * L, g], [0.03 * L, g]]).buffer(0)
        big = lambda q: max(getattr(q, "geoms", [q]), key=lambda t: t.area)
        low, cab = big(full.intersection(box(-1, -1, L + 1, zb))), big(full.intersection(box(-1, zb, L + 1, H + 1)))
        body_prof = [list(q) for q in low.simplify(0.003 * L).exterior.coords[:-1]]
        cab_prof = [list(q) for q in cab.simplify(0.003 * L).exterior.coords[:-1]]
        n = len(cab_prof)
        on = [i for i in range(n) if abs(cab_prof[i][1] - zb) < 1e-6 and abs(cab_prof[(i + 1) % n][1] - zb) < 1e-6]
        cab_hidden = max(on, key=lambda i: abs(cab_prof[i][0] - cab_prof[(i + 1) % n][0]))
        xs_ = [x for x, _ in cab_prof]
        ws, re = min(xs_), max(xs_)
        glass_side = cab.buffer(-0.05)
    solids = [
        {"type": "prism", "name": "Nadwozie", "axis": "y", "group": "body", "color": col, "from": -W / 2, "to": W / 2,
         "profile": body_prof},
        {"type": "prism", "name": "Kabina", "axis": "y", "group": "cabin", "color": col, "from": -hw, "to": hw,
         "hidden": [cab_hidden], "profile": cab_prof},
    ]
    fo = (L - wb) * 0.47
    axles = [fo, fo + wb]
    P = []
    for x in axles:   # wnęki kół
        arc = [[x + 1.18 * r * math.cos(math.pi * k / 12), r + 1.18 * r * math.sin(math.pi * k / 12)] for k in range(13)]
        P.append({"view": "side", "polygon": [[x + 1.18 * r, g]] + arc + [[x - 1.18 * r, g]], "color": "#141414", "groups": ["body"]})
    glass = "#f7f7f5" if wnetrze else GLASS
    mid = (ws + sw + re - sr) / 2
    win = [[[ws + 0.035 * L, zb + 0.03], [mid - 0.02, zb + 0.03], [mid - 0.02, H - 0.07], [ws + sw + 0.02, H - 0.07]],
           [[mid + 0.02, zb + 0.03], [re - 0.035 * L, zb + 0.03], [re - sr - 0.02, H - 0.07], [mid + 0.02, H - 0.07]]]
    if glass_side is not None and not glass_side.is_empty:
        from shapely.geometry import box as _box
        mid = glass_side.centroid.x
        parts = glass_side.difference(_box(mid - 0.025, 0, mid + 0.025, H + 1))
        win = [[list(q) for q in t.simplify(0.01).exterior.coords[:-1]] for t in getattr(parts, "geoms", [parts])
               if t.geom_type == "Polygon" and t.area > 0.01]
    for poly in win:
        P.append({"view": "side", "polygon": poly, "color": glass, "groups": ["cabin"]})
        if wnetrze:
            P.append({"view": "side", "line": poly + [poly[0]], "color": "#c0261a", "width": 0.5, "groups": ["cabin"]})
    for view in ("front", "back"):
        rect = [-hw * 0.86, zb + 0.04, hw * 0.86, H - 0.06]
        P.append({"view": view, "rect": rect, "color": glass, "groups": ["cabin"], "min_dot": 0.2})
        if wnetrze:
            x0, y0, x1, y1 = rect
            P.append({"view": view, "line": [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]], "color": "#c0261a",
                      "width": 0.5, "groups": ["cabin"], "min_dot": 0.2})
    zl = g + 0.62 * (zb - g)
    for sy in (-1, 1):
        P.append({"view": "front", "polygon": [[sy * 0.33 * W + 0.075 * math.cos(a / 8 * math.pi), zl + 0.075 * math.sin(a / 8 * math.pi)]
                                               for a in range(16)], "color": "#f1ecd2", "groups": ["body"], "min_dot": 0.2})
        P.append({"view": "back", "rect": sorted([sy * 0.40 * W, sy * 0.27 * W])[:1] + [zl - 0.05] + sorted([sy * 0.40 * W, sy * 0.27 * W])[1:] + [zl + 0.05],
                  "color": "#b3261e", "groups": ["body"], "min_dot": 0.2})
    for view in ("front", "back"):   # zderzaki
        P.append({"view": view, "rect": [-0.47 * W, g + 0.14, 0.47 * W, g + 0.22], "color": "#c9ccd0", "groups": ["body"], "min_dot": 0.2})
    P += panel_line("side", [[mid, g + 0.12], [mid, zb]], ["body"])          # drzwi
    P += panel_line("side", [[ws + 0.02 * L, g + 0.12], [ws + 0.02 * L, zb]], ["body"])
    P += panel_line("side", [[0.02 * L, zb - 0.12], [L - 0.02 * L, zb - 0.12]], ["body"])
    P += panel_line("top", [[ws - 0.02, -0.42 * W], [ws - 0.02, 0.42 * W]], ["body"])
    P.append({"view": "side", "rect": [0, g, L, g + 0.10], "color": "#3a3026", "alpha": 0.22, "groups": ["body"]})
    spec = {
        "name": f["nazwa"], "variant": f.get("wariant", "") + (" (z wnętrzem)" if wnetrze else ""), "solids": solids,
        "wheels": [{"name": "Koło", "r": r, "width": 0.14, "centers": [[x, W / 2 - 0.09, r] for x in axles],
                    "color": "#c9ccd0", "hub_color": "#8d9399"}],
        "paint": P, "notes": ["Koła sklej z warstw tektury, oklej tarczami i bieżnikiem, przyklej we wnękach."],
    }
    if wnetrze:
        seat = lambda name, x, y: [
            {"type": "box", "name": f"{name} – siedzisko", "group": "seat", "color": "#5a4a3a", "hidden": ["from"],
             "at": [x, y - 0.21, zb], "size": [0.42, 0.42, 0.12]},
            {"type": "box", "name": f"{name} – oparcie", "group": "seat", "color": "#5a4a3a", "hidden": ["from"],
             "at": [x + 0.44, y - 0.21, zb], "size": [0.08, 0.42, min(0.42, H - zb - 0.12)]}]
        x1 = ws + sw + 0.05
        solids += seat("Fotel kierowcy", x1, -0.22 * W) + seat("Fotel pasażera", x1, 0.22 * W)
        spec["notes"].append("Okna obwiedzione czerwoną linią wytnij i wklej od środka przezroczystą folię; "
                             "fotele przyklej do podłogi przed zamknięciem kabiny.")
    return spec


REF = {"bf109e": (8.64, 9.87), "p51d": (9.83, 11.28)}   # długość i rozpiętość wzorców


def aircraft(f: dict, **_) -> dict:
    """Jednosilnikowy dolnopłat: wzorzec przeskalowany do długości i rozpiętości, z własnym malowaniem."""
    import copy

    from .aircraft import load_specs
    key = f.get("wzor", "bf109e") if f.get("wzor") in REF else "bf109e"
    spec = copy.deepcopy(load_specs()[key])
    kx, ky = f["dlugosc"] / REF[key][0], f["rozpietosc"] / REF[key][1]
    spec["name"], spec["variant"] = f["nazwa"], f.get("wariant", "")
    for st in spec["fuselage"]["stations"]:
        st[:5] = [v * kx for v in st[:5]]
    spec["spinner"] = [[x * kx, r * kx] for x, r in spec["spinner"]]
    c = spec["canopy"]
    c["z0"], c["hw"], c["h"] = c["z0"] * kx, c["hw"] * kx, c["h"] * kx
    c["sections"] = [[x * kx, a, b] for x, a, b in c["sections"]]
    spec["wing"]["sections"] = [[x * kx, y * ky, z * kx, ch * kx, t] for x, y, z, ch, t in spec["wing"]["sections"]]
    spec["wing"]["spar_x"] *= kx
    for k in ("stab", "fin"):
        spec[k]["sections"] = [[x * kx, y * kx, z * kx, ch * kx, t] for x, y, z, ch, t in spec[k]["sections"]]
    for k in ("radius", "chord", "hub", "x"):
        spec["prop"][k] *= kx
    g = spec["gear"]
    spec["gear"] = {"x": g["x"] * kx, "y": g["y"] * ky, "z_top": g["z_top"] * kx, "leg": g["leg"] * kx, "wheel_r": g["wheel_r"] * kx}
    spec["exhaust"] = [v * kx for v in spec["exhaust"]]
    top, low = f.get("kolor_gora", "#5b6b4f"), f.get("kolor_dol", "#a9c3cf")
    spec["colors"] = {"base": low, "spinner": f.get("kolor_kolpaka", top)}
    half = spec["wing"]["sections"][-2][1]
    wx = spec["wing"]["sections"][0][0] + 0.5 * spec["wing"]["sections"][0][3]
    P = [{"view": "top", "polygon": "all", "color": top, "groups": ["fuselage"], "min_dot": 0.3},
         {"view": "side", "polygon": "all", "color": top, "groups": ["fuselage", "fin"], "min_dot": 0.55},
         {"view": "top", "polygon": "all", "color": top, "groups": ["wing", "stab"], "min_dot": 0.05}]
    if f.get("znak"):
        P += [{"view": "side", "insignia": f["znak"], "at": [0.63 * f["dlugosc"], 0.06 * kx], "size": 0.6 * kx, "groups": ["fuselage"]},
              {"view": "top", "insignia": f["znak"], "at": [wx, 0.68 * half], "size": 0.85 * kx, "mirror": True, "groups": ["wing"], "min_dot": 0.05},
              {"view": "bottom", "insignia": f["znak"], "at": [wx, 0.68 * half], "size": 0.85 * kx, "mirror": True, "groups": ["wing"], "min_dot": 0.05}]
    spec["paint"] = P
    return spec


TEMPLATES = {"czolg": tank, "samochod": car, "samolot": aircraft}
