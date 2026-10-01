"""
P-51-like Mini-Haliński unfold — własna geometria parametryczna.

Architektura (jak w prawdziwych wycinankach lotniczych):
- formers/ribs/spar → tektura 1 mm (laminat *)
- skóry = rozwinięcia stożka ściętego / planform skrzydła
- bez kopiowania cudzych plansz (tylko konwencje konstrukcyjne)
"""

from __future__ import annotations

import math

from .box_unfold import FacePanel, Point, UnfoldResult


STATION_LABELS = list("ABCDEFGHIJ")


def unfold_fighter(
    fuselage_length_mm: float = 205.0,
    fuselage_diameter_mm: float = 26.0,
    wingspan_mm: float = 235.0,
    wing_chord_mm: float = 36.0,
    wing_tip_chord_mm: float | None = None,
    wing_thickness_mm: float = 5.5,
    tailplane_span_mm: float = 72.0,
    tailplane_chord_mm: float = 20.0,
    fin_height_mm: float = 30.0,
    fin_chord_mm: float = 26.0,
    flap_mm: float = 4.0,
    margin_mm: float = 5.0,
    stations: int = 10,
) -> UnfoldResult:
    tip_chord = wing_tip_chord_mm if wing_tip_chord_mm is not None else wing_chord_mm * 0.42
    F = flap_mm
    L = fuselage_length_mm
    Dmax = fuselage_diameter_mm
    n = max(6, min(stations, 10))

    factors = _mustang_diameter_factors(n)
    diams = [max(7.5, Dmax * f) for f in factors]
    # stacje nierównomierne (gęściej przy nosie/kokpicie)
    station_t = _station_positions(n)
    station_x = [L * t for t in station_t]

    panels: list[FacePanel] = []
    cursor_x = margin_mm + F
    cursor_y = margin_mm + F
    pid = 1

    def bump(panel: FacePanel, gap: float = 3.5, row_limit: float = 195.0) -> None:
        nonlocal cursor_x, cursor_y, pid
        panels.append(panel)
        pid += 1
        cursor_x = panel.x + panel.w + gap
        if cursor_x > row_limit:
            cursor_x = margin_mm + F
            cursor_y = max(p.y + p.h for p in panels) + gap + 2

    # ========== SZKIELET: wręgi A–J ==========
    row_x, row_y = cursor_x, cursor_y
    for i, d in enumerate(diams):
        lab = STATION_LABELS[i] if i < len(STATION_LABELS) else str(i)
        r = d / 2
        # elipsa Mustang: nieco wyższa w części kabiny
        ry = r * (1.05 if 0.25 < station_t[i] < 0.55 else 0.92)
        panel = _former_with_notch(
            str(pid),
            f"former_{lab}",
            f"{lab}*",
            row_x + r + 1,
            row_y + max(r, ry) + 1,
            r,
            ry,
            notch=max(1.2, F * 0.35),
        )
        panels.append(panel)
        pid += 1
        row_x += 2 * r + F + 4
        if row_x > 185:
            row_x = margin_mm + F
            row_y = max(p.y + p.h for p in panels) + F + 3

    # keel / stringer
    keel_len = L * 0.92
    keel = _rect_strip(
        str(pid), "keel", "Keel*", cursor_x, max(p.y + p.h for p in panels) + 6, keel_len, 3.2
    )
    bump(keel, gap=5)

    # ========== POSZYCIE KADŁUBA: pierścienie (pół-obwód L/P) ==========
    cursor_y = max(p.y + p.h for p in panels) + 8
    cursor_x = margin_mm + F

    for i in range(n - 1):
        seg = station_x[i + 1] - station_x[i]
        da, db = diams[i], diams[i + 1]
        la = STATION_LABELS[i] if i < len(STATION_LABELS) else str(i)
        lb = STATION_LABELS[i + 1] if i + 1 < len(STATION_LABELS) else str(i + 1)
        for side, sfx in (("L", "L"), ("R", "R")):
            panel = _frustum_half_skin(
                str(pid),
                f"fuse_{sfx}{la}{lb}",
                f"{i + 1}{sfx}",
                cursor_x,
                cursor_y,
                da,
                db,
                seg,
                F,
                mirror=(side == "R"),
            )
            bump(panel, gap=3.5, row_limit=188)

    # chłodnica (scoop) — trapez z zakładkami
    rad = _tapered_quad(
        str(pid),
        "radiator_scoop",
        "Scoop",
        cursor_x,
        cursor_y,
        L * 0.24,
        Dmax * 0.55,
        Dmax * 0.85,
        F,
    )
    bump(rad, gap=6)

    # ========== SKRZYDŁA ==========
    half = wingspan_mm / 2
    root, tip = wing_chord_mm, tip_chord

    for side, sfx in (("L", "left"), ("R", "right")):
        # dźwigar
        spar = _rect_strip(
            str(pid),
            f"spar_{sfx}",
            f"Spar {side}*",
            cursor_x,
            cursor_y,
            half * 0.92,
            4.0,
        )
        bump(spar, gap=4)

        # żebra (6)
        for ri, span_pos in enumerate((0.08, 0.22, 0.40, 0.58, 0.75, 0.90)):
            chord_i = root + (tip - root) * span_pos
            thick = wing_thickness_mm * (1.0 - 0.4 * span_pos)
            rib = _wing_rib(
                str(pid),
                f"rib_{sfx}_{ri}",
                f"R{side}{ri}*",
                cursor_x,
                cursor_y,
                chord_i,
                thick,
            )
            bump(rib, gap=2.5, row_limit=200)

        # wheel well box (wnęka)
        well = _wheel_well_box(
            str(pid),
            f"well_{sfx}",
            f"Well {side}",
            cursor_x,
            cursor_y,
            root * 0.55,
            root * 0.35,
            wing_thickness_mm * 1.1,
            F,
        )
        bump(well, gap=4)

        for surf, lab in (("upper", "góra"), ("lower", "spód")):
            wing = _wing_skin(
                str(pid),
                f"wing_{sfx}_{surf}",
                f"W{side[0]}{'u' if surf == 'upper' else 'l'}",
                cursor_x,
                cursor_y,
                half,
                root,
                tip,
                F,
                mirror=(side == "R"),
                well_cutout=(surf == "lower"),
            )
            bump(wing, gap=4, row_limit=160)

        # LE wrap trapez
        le = _tapered_quad(
            str(pid),
            f"wing_{sfx}_le",
            f"LE {side}",
            cursor_x,
            cursor_y,
            half,
            max(7.0, math.pi * wing_thickness_mm / 2),
            max(4.0, math.pi * wing_thickness_mm / 2 * 0.55),
            0,
        )
        bump(le, gap=4)

        # klapa + lotka
        flap_p = _control_surface(
            str(pid), f"flap_{sfx}", f"Flap {side}", cursor_x, cursor_y,
            half * 0.40, root * 0.20, root * 0.16, F, mirror=(side == "R"),
        )
        bump(flap_p, gap=3)
        ail = _control_surface(
            str(pid), f"aileron_{sfx}", f"Ail {side}", cursor_x, cursor_y,
            half * 0.36, tip * 0.50, tip * 0.40, F, mirror=(side == "R"),
        )
        bump(ail, gap=5)

    # ========== KABINA ==========
    for ci, clab in enumerate(("L", "Top", "P")):
        canopy = _canopy_panel(
            str(pid), f"canopy_{ci}", f"Canopy {clab}",
            cursor_x, cursor_y, L * 0.15, Dmax * (0.5 if ci == 1 else 0.38), F,
        )
        bump(canopy, gap=3)

    # ========== USTERZENIE ==========
    tp_half = tailplane_span_mm / 2
    tp_root, tp_tip = tailplane_chord_mm, tailplane_chord_mm * 0.55
    for side, sfx in (("L", "left"), ("R", "right")):
        for surf, _ in (("upper", "g"), ("lower", "s")):
            tp = _wing_skin(
                str(pid), f"tailplane_{sfx}_{surf}", f"TP{side[0]}",
                cursor_x, cursor_y, tp_half, tp_root, tp_tip, F,
                mirror=(side == "R"), well_cutout=False,
            )
            bump(tp, gap=3, row_limit=170)

    fin = _fin_panel(str(pid), "fin", "Fin", cursor_x, cursor_y, fin_chord_mm, fin_height_mm, F)
    bump(fin, gap=4)
    rudder = _fin_panel(
        str(pid), "rudder", "Rudder", cursor_x, cursor_y,
        fin_chord_mm * 0.42, fin_height_mm * 0.85, F, rudder=True,
    )
    bump(rudder, gap=6)

    # ========== ŚMIGŁO + SPINNER ==========
    for bi in range(4):
        blade = _prop_blade(
            str(pid), f"prop_{bi}", f"Prop {bi + 1}",
            cursor_x, cursor_y, Dmax * 1.55, Dmax * 0.28, F,
        )
        bump(blade, gap=2.5)
    for gi in range(4):
        gore = _spinner_gore(
            str(pid), f"spinner_{gi}", f"Spin {gi + 1}",
            cursor_x, cursor_y, Dmax * 0.45, F,
        )
        bump(gore, gap=2)

    max_x = max(_panel_max(p)[0] for p in panels) + margin_mm
    max_y = max(_panel_max(p)[1] for p in panels) + margin_mm

    return UnfoldResult(
        panels=panels,
        width_mm=max_x,
        height_mm=max_y,
        instructions=[
            "1. Formierze A–J i żebra (*) — podklej na tekturę 1 mm, wytnij, złóż na keel.",
            "2. Nos: uformuj pierścień fuse_*AB / BC, doklej do wręg A–C.",
            "3. Kolejne sekcje kadłuba L/P na wręgach; dociśnij szwy generatorów.",
            "4. Kabina przed zamknięciem grzbietu; canopy L/Top/P.",
            "5. Skrzydło: spar + żebra + well → skóra góra/spód → LE → flap/aileron.",
            "6. Usterzenie, ster, spinner (4 gores) + 4 łopaty śmigła.",
            "7. Scoop chłodnicy na spodzie; sprawdź symetrię dihedral.",
        ],
    )


def split_formers_and_skins(result: UnfoldResult) -> tuple[UnfoldResult, UnfoldResult]:
    """Rozdziel szkielet (laminat) od skór kolorowych."""
    formers = [
        p
        for p in result.panels
        if p.name.startswith(("former_", "rib_", "spar_", "keel"))
    ]
    skins = [p for p in result.panels if p not in formers]
    return (
        UnfoldResult(
            panels=formers,
            width_mm=result.width_mm,
            height_mm=result.height_mm,
            instructions=["Szkielet — podklej na tekturę 1–1,5 mm przed cięciem (*)."],
        ),
        UnfoldResult(
            panels=skins,
            width_mm=result.width_mm,
            height_mm=result.height_mm,
            instructions=result.instructions,
        ),
    )


# ----- geometria pomocnicza -----


def _mustang_diameter_factors(n: int) -> list[float]:
    keys = [0.0, 0.12, 0.22, 0.35, 0.48, 0.58, 0.70, 0.82, 0.92, 1.0]
    vals = [0.48, 0.72, 0.92, 1.00, 0.98, 0.88, 0.72, 0.55, 0.42, 0.32]
    out = []
    for i in range(n):
        t = i / (n - 1)
        for k in range(len(keys) - 1):
            if keys[k] <= t <= keys[k + 1]:
                u = (t - keys[k]) / (keys[k + 1] - keys[k])
                out.append(vals[k] * (1 - u) + vals[k + 1] * u)
                break
        else:
            out.append(vals[-1])
    return out


def _station_positions(n: int) -> list[float]:
    # gęściej przy nosie i kabinie
    raw = [i / (n - 1) for i in range(n)]
    return [0.55 * t + 0.45 * (t ** 1.35) for t in raw]


def _former_with_notch(
    pid: str, name: str, label: str, cx: float, cy: float, rx: float, ry: float, notch: float
) -> FacePanel:
    """Gładka elipsa (72 seg) + otwór keel — bez nitów/„kwadratowego koła”."""
    segs = 72
    pts: list[Point] = []
    for i in range(segs):
        a = -math.pi / 2 + 2 * math.pi * i / segs
        pts.append(Point(cx + rx * math.cos(a), cy + ry * math.sin(a)))
    nw = max(1.0, notch * 0.7)
    nh = max(1.2, notch)
    hole = [
        Point(cx - nw, cy + ry - nh * 0.3),
        Point(cx + nw, cy + ry - nh * 0.3),
        Point(cx + nw, cy + ry + 0.15),
        Point(cx - nw, cy + ry + 0.15),
    ]
    return FacePanel(
        id=pid,
        name=name,
        label=label,
        x=cx - rx,
        y=cy - ry,
        w=2 * rx,
        h=2 * ry + 0.15,
        cut_paths=[pts, hole],
        fold_lines=[
            (Point(cx, cy - ry * 0.85), Point(cx, cy + ry * 0.55)),
        ],
    )


def _frustum_half_skin(
    pid: str,
    name: str,
    label: str,
    x: float,
    y: float,
    d1: float,
    d2: float,
    length: float,
    flap_mm: float,
    mirror: bool = False,
) -> FacePanel:
    """Rozwinięcie pół-stożka = wycinek pierścienia (nie trapez)."""
    r1, r2 = max(0.5, d1 / 2), max(0.5, d2 / 2)
    segs = 28

    if abs(r2 - r1) < 0.2:
        h = math.pi * ((r1 + r2) / 2)
        mid = Point(x + length / 2, y + h / 2)
        top = _sample(Point(x, y), Point(x + length, y), 10, bulge=0.5, toward=mid)
        bot = _sample(Point(x + length, y + h), Point(x, y + h), 10, bulge=0.5, toward=mid)
        outline = top + bot
        w, hbox = length, h
    else:
        slant = math.hypot(length, r2 - r1)
        R_big = max(r1, r2) * slant / abs(r2 - r1)
        R_sml = min(r1, r2) * slant / abs(r2 - r1)
        phi = math.pi * abs(r2 - r1) / slant
        outline = []
        for i in range(segs + 1):
            a = -phi / 2 + phi * i / segs
            outline.append(Point(R_big * math.sin(a), -R_big * math.cos(a)))
        for i in range(segs, -1, -1):
            a = -phi / 2 + phi * i / segs
            outline.append(Point(R_sml * math.sin(a), -R_sml * math.cos(a)))
        minx = min(p.x for p in outline)
        miny = min(p.y for p in outline)
        outline = [Point(p.x - minx + x, p.y - miny + y) for p in outline]
        w = max(p.x for p in outline) - x
        hbox = max(p.y for p in outline) - y
        if r1 > r2:
            maxx = x + w
            outline = [Point(maxx - (p.x - x), p.y) for p in outline]

    if mirror:
        mid_x = x + w / 2
        outline = [Point(2 * mid_x - p.x, p.y) for p in outline]

    panel = FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=w, h=hbox,
        cut_paths=[outline], fold_lines=[],
    )
    a, b = outline[0], outline[-1]
    flap = [
        a,
        Point(a.x - flap_mm, a.y + 0.8),
        Point(b.x - flap_mm, b.y - 0.8),
        b,
    ]
    panel.flaps.append(flap)
    panel.cut_paths.append(flap)
    panel.fold_lines.append((a, b))
    xs = [p.x for p in outline] + [p.x for p in flap]
    ys = [p.y for p in outline] + [p.y for p in flap]
    panel.x = min(xs)
    panel.y = min(ys)
    panel.w = max(xs) - panel.x
    panel.h = max(ys) - panel.y
    return panel


def _sample(a: Point, b: Point, n: int, bulge: float = 0.0, toward: Point | None = None) -> list[Point]:
    pts = []
    dx, dy = b.x - a.x, b.y - a.y
    L = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / L, dx / L
    if toward is not None:
        mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
        if (toward.x - mx) * nx + (toward.y - my) * ny < 0:
            nx, ny = -nx, -ny
    for i in range(n + 1):
        t = i / n
        bamt = bulge * math.sin(math.pi * t)
        pts.append(Point(a.x + dx * t + nx * bamt, a.y + dy * t + ny * bamt))
    return pts


def _wing_skin(
    pid: str,
    name: str,
    label: str,
    x: float,
    y: float,
    span: float,
    root: float,
    tip: float,
    flap_mm: float,
    mirror: bool = False,
    well_cutout: bool = False,
) -> FacePanel:
    le_sweep = (root - tip) * 0.22
    te_sweep = (root - tip) * 0.55
    tip_r = max(3.5, tip * 0.4)
    tip_segs = 10

    if not mirror:
        le_root = Point(x, y)
        te_root = Point(x, y + root)
        le_tip = Point(x + span - tip_r * 0.35, y + le_sweep)
        te_tip = Point(x + span - tip_r * 0.35, y + root - te_sweep)
        le = _sample(le_root, le_tip, 6, bulge=-1.0)
        tip_cx, tip_cy = x + span, (le_tip.y + te_tip.y) / 2
        ry = max(2.0, (te_tip.y - le_tip.y) / 2)
        tip_pts = [
            Point(tip_cx + tip_r * math.cos(a) * 0.95, tip_cy + ry * math.sin(a))
            for a in [-math.pi / 2 + math.pi * i / tip_segs for i in range(tip_segs + 1)]
        ]
        te = _sample(Point(tip_pts[-1].x, tip_pts[-1].y), te_root, 6, bulge=0.7)
        pts = le[:-1] + tip_pts + te[1:]
    else:
        le_root = Point(x + span, y)
        te_root = Point(x + span, y + root)
        le_tip = Point(x + tip_r * 0.35, y + le_sweep)
        te_tip = Point(x + tip_r * 0.35, y + root - te_sweep)
        le = _sample(le_root, le_tip, 6, bulge=-1.0)
        tip_cx, tip_cy = x, (le_tip.y + te_tip.y) / 2
        ry = max(2.0, (te_tip.y - le_tip.y) / 2)
        tip_pts = [
            Point(tip_cx + tip_r * math.cos(a) * 0.95, tip_cy + ry * math.sin(a))
            for a in [math.pi / 2 + math.pi * i / tip_segs for i in range(tip_segs + 1)]
        ]
        te = _sample(Point(tip_pts[-1].x, tip_pts[-1].y), te_root, 6, bulge=0.7)
        pts = le[:-1] + tip_pts + te[1:]

    xs, ys = [p.x for p in pts], [p.y for p in pts]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    panel = FacePanel(
        id=pid, name=name, label=label,
        x=minx, y=miny, w=maxx - minx, h=maxy - miny,
        cut_paths=[pts], fold_lines=[],
    )

    # wheel well — otwór w skórze dolnej
    if well_cutout:
        wx = x + span * 0.12 if not mirror else x + span * 0.55
        wy = y + root * 0.35
        ww, wh = root * 0.42, root * 0.28
        well = [
            Point(wx, wy), Point(wx + ww, wy),
            Point(wx + ww, wy + wh), Point(wx, wy + wh),
        ]
        panel.cut_paths.append(well)

    # zakładka root
    root_le, root_te = pts[0], pts[-1]
    if not mirror:
        flap = [
            root_le, Point(root_le.x - flap_mm, root_le.y + 2),
            Point(root_te.x - flap_mm, root_te.y - 2), root_te,
        ]
        panel.x = minx - flap_mm
        panel.w = (maxx - minx) + flap_mm
    else:
        flap = [
            root_le, Point(root_le.x + flap_mm, root_le.y + 2),
            Point(root_te.x + flap_mm, root_te.y - 2), root_te,
        ]
        panel.w = (maxx - minx) + flap_mm
    panel.flaps.append(flap)
    panel.cut_paths.append(flap)
    panel.fold_lines.append((root_le, root_te))
    return panel


def _wing_rib(pid: str, name: str, label: str, x: float, y: float, chord: float, thick: float) -> FacePanel:
    t, c = thick, chord
    pts = [
        Point(x, y + t * 0.45),
        Point(x + c * 0.12, y),
        Point(x + c * 0.40, y + t * 0.04),
        Point(x + c * 0.70, y + t * 0.18),
        Point(x + c, y + t * 0.38),
        Point(x + c * 0.70, y + t * 0.72),
        Point(x + c * 0.40, y + t * 0.95),
        Point(x + c * 0.12, y + t),
    ]
    # slot na spar
    sx = x + c * 0.28
    slot = [
        Point(sx, y + t * 0.35), Point(sx + 2.2, y + t * 0.35),
        Point(sx + 2.2, y + t * 0.65), Point(sx, y + t * 0.65),
    ]
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=c, h=t,
        cut_paths=[pts, slot], fold_lines=[],
    )


def _wheel_well_box(
    pid: str, name: str, label: str, x: float, y: float, w: float, d: float, h: float, flap_mm: float
) -> FacePanel:
    """Net pudełka wnęki: dno + 4 ścianki w krzyżu."""
    # uproszczenie: dno + jeden pasek ścian
    pts = [
        Point(x, y), Point(x + w, y), Point(x + w, y + d), Point(x, y + d),
    ]
    wall = [
        Point(x, y + d), Point(x + w, y + d),
        Point(x + w, y + d + h), Point(x, y + d + h),
    ]
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=w, h=d + h,
        cut_paths=[pts, wall],
        fold_lines=[(Point(x, y + d), Point(x + w, y + d))],
    )


def _control_surface(
    pid, name, label, x, y, span, root_c, tip_c, flap_mm, mirror=False
) -> FacePanel:
    if not mirror:
        pts = [
            Point(x, y),
            Point(x + span, y + (root_c - tip_c) * 0.35),
            Point(x + span, y + (root_c - tip_c) * 0.35 + tip_c),
            Point(x, y + root_c),
        ]
    else:
        pts = [
            Point(x + span, y),
            Point(x, y + (root_c - tip_c) * 0.35),
            Point(x, y + (root_c - tip_c) * 0.35 + tip_c),
            Point(x + span, y + root_c),
        ]
    h = root_c + abs(root_c - tip_c) * 0.35
    panel = FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=span, h=h,
        cut_paths=[pts], fold_lines=[(pts[0], pts[3])],
    )
    if not mirror:
        flap = [pts[0], Point(x - flap_mm, y + 1), Point(x - flap_mm, y + root_c - 1), pts[3]]
        panel.x = x - flap_mm
        panel.w = span + flap_mm
    else:
        flap = [
            pts[0], Point(x + span + flap_mm, y + 1),
            Point(x + span + flap_mm, y + root_c - 1), pts[3],
        ]
        panel.w = span + flap_mm
    panel.flaps.append(flap)
    panel.cut_paths.append(flap)
    return panel


def _tapered_quad(pid, name, label, x, y, length, h_left, h_right, flap_mm) -> FacePanel:
    h = max(h_left, h_right)
    dy_l = (h - h_left) / 2
    dy_r = (h - h_right) / 2
    pts = [
        Point(x, y + dy_l), Point(x + length, y + dy_r),
        Point(x + length, y + dy_r + h_right), Point(x, y + dy_l + h_left),
    ]
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=length, h=h,
        cut_paths=[pts], fold_lines=[],
    )


def _canopy_panel(pid, name, label, x, y, length, width, flap_mm) -> FacePanel:
    pts = []
    for i in range(12):
        t = i / 11
        pts.append(Point(x + length * t, y + width - math.sin(math.pi * t) * width))
    pts.append(Point(x + length, y + width))
    pts.append(Point(x, y + width))
    panel = FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=length, h=width + flap_mm,
        cut_paths=[pts],
        fold_lines=[(Point(x, y + width), Point(x + length, y + width))],
    )
    flap = [
        Point(x, y + width), Point(x + length, y + width),
        Point(x + length - 1, y + width + flap_mm), Point(x + 1, y + width + flap_mm),
    ]
    panel.flaps.append(flap)
    panel.cut_paths.append(flap)
    return panel


def _fin_panel(pid, name, label, x, y, chord, height, flap_mm, rudder=False) -> FacePanel:
    sweep = chord * (0.35 if not rudder else 0.18)
    tip_c = chord * (0.55 if not rudder else 0.7)
    pts = [
        Point(x, y + height), Point(x + sweep, y),
        Point(x + sweep + tip_c, y), Point(x + chord, y + height),
    ]
    panel = FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=chord + sweep, h=height + flap_mm,
        cut_paths=[pts], fold_lines=[(pts[0], pts[3])],
    )
    flap = [
        Point(x, y + height), Point(x + chord, y + height),
        Point(x + chord - 1.5, y + height + flap_mm), Point(x + 1.5, y + height + flap_mm),
    ]
    panel.flaps.append(flap)
    panel.cut_paths.append(flap)
    return panel


def _prop_blade(pid, name, label, x, y, length, width, flap_mm) -> FacePanel:
    # łopata: kropla wydłużona
    pts = []
    for i in range(12):
        t = i / 11
        # chord profile along span
        ww = width * (0.35 + 0.65 * math.sin(math.pi * t))
        pts.append(Point(x + length * t, y + width / 2 - ww / 2))
    for i in range(11, -1, -1):
        t = i / 11
        ww = width * (0.35 + 0.65 * math.sin(math.pi * t))
        pts.append(Point(x + length * t, y + width / 2 + ww / 2))
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=length, h=width,
        cut_paths=[pts], fold_lines=[],
    )


def _spinner_gore(pid, name, label, x, y, radius, flap_mm) -> FacePanel:
    w = radius * 1.2
    h = radius * 1.65
    pts = [
        Point(x + w / 2, y),
        Point(x + w, y + h * 0.85),
        Point(x + w * 0.7, y + h),
        Point(x + w * 0.3, y + h),
        Point(x, y + h * 0.85),
    ]
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=w, h=h,
        cut_paths=[pts], fold_lines=[],
    )


def _rect_strip(pid, name, label, x, y, w, h) -> FacePanel:
    pts = [Point(x, y), Point(x + w, y), Point(x + w, y + h), Point(x, y + h)]
    return FacePanel(
        id=pid, name=name, label=label, x=x, y=y, w=w, h=h,
        cut_paths=[pts],
        fold_lines=[(Point(x, y + h / 2), Point(x + w, y + h / 2))],
    )


def _panel_max(panel: FacePanel) -> tuple[float, float]:
    xs, ys = [], []
    for path in panel.cut_paths:
        for p in path:
            xs.append(p.x)
            ys.append(p.y)
    return (
        max(xs) if xs else panel.x + panel.w,
        max(ys) if ys else panel.y + panel.h,
    )
