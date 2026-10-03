"""Bramka jakości: arkusz ma wynikać z bryły i dać się skleić."""
import math
import shutil
import subprocess

import numpy as np
import pytest
from shapely.geometry import Polygon

from modelarz.layout import MARGIN, PAGES, PackError
from modelarz.models import REGISTRY, AircraftParams, BoxParams, FrustumParams, HouseParams
from modelarz.models import build_box, build_frustum, build_house
from modelarz.pdf import RULER_MM, RULER_Y, find_fonts, write_pdf
from modelarz.preview import preview_data
from modelarz.project import build_project
from modelarz.seams import MIN_TAB_EDGE
from modelarz.validate import validate

CASES = {
    "pudelko": (build_box, BoxParams(), "A4"),
    "pudelko-plaskie": (build_box, BoxParams(width=150, depth=90, height=12), "A4"),
    "domek": (build_house, HouseParams(), "A4"),
    "domek-dlugi": (build_house, HouseParams(width=70, length=160, wall=60, roof=40), "A4"),
    "stozek-sciety": (build_frustum, FrustumParams(), "A4"),
    "walec": (build_frustum, FrustumParams(r_bottom=25, r_top=25, height=80), "A4"),
    "stozek": (build_frustum, FrustumParams(r_bottom=35, r_top=0, height=70, segments=16), "A4"),
    "p51d": (REGISTRY["p51d"][2], AircraftParams(), "A4"),
    "p51d-latwy-48": (REGISTRY["p51d"][2], AircraftParams(scale=48, level=1), "A4"),
    "p51d-trudny-a3": (REGISTRY["p51d"][2], AircraftParams(scale=24, level=3), "A3"),
    "bf109e": (REGISTRY["bf109e"][2], AircraftParams(), "A4"),
    "bf109e-latwy": (REGISTRY["bf109e"][2], AircraftParams(level=1), "A4"),
    "bf109e-trudny-48": (REGISTRY["bf109e"][2], AircraftParams(scale=48, level=3), "A4"),
}


@pytest.fixture(scope="module", params=list(CASES))
def project(request):
    build, params, page = CASES[request.param]
    return build_project(build(params), page)


def test_wszystkie_kontrole_przechodza(project):
    failed = [f"{c.name}: {c.detail}" for c in validate(project) if not c.ok]
    assert not failed, failed


def test_bryla_zamknieta_i_zorientowana(project):
    mesh = project.model.mesh
    # krawędź otwarta może być tylko miejscem doklejenia do innej bryły (po docięciu)
    assert all(len(v) == 2 or (len(v) == 1 and k in mesh.attach) for k, v in mesh.edges().items())
    assert mesh.volume() > 0


def test_rozwiniecie_zachowuje_pole_powierzchni(project):
    mesh = project.model.mesh
    for pc in project.pieces:
        flat = sum(Polygon(pf.pts).area for pf in pc.faces)
        solid = 0.0
        for pf in pc.faces:
            p = mesh.face_points(pf.face)
            solid += 0.5 * np.linalg.norm(sum(np.cross(p[i] - p[0], p[i + 1] - p[0]) for i in range(1, len(p) - 1)))
        assert flat == pytest.approx(solid, abs=1e-6)
        assert pc.body.area == pytest.approx(flat, abs=1e-4)   # ściany nie nachodzą na siebie


def test_kazdy_szew_ma_zakladki_po_jednej_stronie(project):
    for sm in project.seams:
        tabbed = [i for i, (pi, poss) in enumerate(sm.sides)
                  if any(project.pieces[pi].boundary[p].tabbed for p in poss)]
        assert len(tabbed) <= 1, f"szew {sm.number} ma zakładki po obu stronach"
        V = project.model.mesh.V
        if any(np.linalg.norm(V[a] - V[b]) >= MIN_TAB_EDGE for a, b in sm.keys):   # krótsze klei się na styk
            assert tabbed == [sm.tab_side], f"szew {sm.number} nie ma zakładek"
        # obie strony szwu noszą ten sam numer
        for pi, poss in sm.sides:
            assert all(project.pieces[pi].boundary[p].seam == sm.number for p in poss)


def test_zakladki_nie_wchodza_na_czesc(project):
    for pc in project.pieces:
        tabs = [t[0] for t in pc.tabs]
        for i, t in enumerate(tabs):
            assert t.is_valid and t.area > 0
            # dopuszczalne 0,02 mm²: prawie współliniowe krawędzie dostają wspólną zakładkę
            assert t.intersection(pc.body).area < 0.02
            assert all(t.intersection(o).area < 0.02 for o in tabs[i + 1:])


def test_podglad_3d_zawiera_cala_bryle(project):
    data = preview_data(project)
    tris = sum(len(m["pos"]) for m in data["meshes"]) // 9
    mesh = project.model.mesh
    assert tris >= sum(1 for f in mesh.faces if not mesh.parts[f.part].virtual) and data["seams"]


# --- bramka naprawdę łapie błędy starej wersji --------------------------------

def _check(pr, name):
    return next(c for c in validate(pr) if c.name == name)


def test_wykrywa_skalowanie_arkusza():
    pr = build_project(build_box(BoxParams()))
    for pf in pr.pieces[0].faces:
        pf.pts = pf.pts * 0.987
    assert not _check(pr, "Skala 1:1 i wierność rozwinięć").ok


def test_wykrywa_samoprzeciecie_obrysu():
    pr = build_project(build_box(BoxParams()))
    b = pr.pieces[0].boundary
    b[0].a, b[1].a = b[1].a, b[0].a
    pr.pieces[0].body = Polygon([e.a for e in b])
    assert not _check(pr, "Obrysy bez samoprzecięć").ok


def test_wykrywa_nakladanie_czesci():
    pr = build_project(build_house(HouseParams()))
    pr.items[1].placement = pr.items[0].placement
    assert not _check(pr, "Rozmieszczenie na arkuszach").ok


def test_wykrywa_niezgodne_dlugosci_szwu():
    pr = build_project(build_house(HouseParams()))
    e = next(e for e in pr.pieces[0].boundary if e.partner is not None)
    e.b = e.a + (e.b - e.a) * 1.05
    assert not _check(pr, "Długości sklejanych krawędzi").ok


def test_za_duza_czesc_to_blad_a_nie_skalowanie():
    with pytest.raises(PackError):
        build_project(build_box(BoxParams(width=250, depth=250, height=250)), "A4")


# --- geometria wzorcowa -----------------------------------------------------

def test_pudelko_objetosc_i_pole():
    pr = build_project(build_box(BoxParams(width=80, depth=50, height=40)))
    assert pr.model.mesh.volume() == pytest.approx(80 * 50 * 40)
    assert sum(pc.body.area for pc in pr.pieces) == pytest.approx(2 * (80 * 50 + 80 * 40 + 50 * 40))


def test_pobocznica_stozka_scietego_ma_wlasciwy_ksztalt():
    p = FrustumParams(r_bottom=30, r_top=18, height=60, segments=48)
    pr = build_project(build_frustum(p))
    side = pr.pieces[0]
    n = p.segments
    chord = lambda r: 2 * r * math.sin(math.pi / n)
    slant = math.hypot(p.height, (p.r_bottom - p.r_top) * math.cos(math.pi / n))
    assert side.body.area == pytest.approx(n * (chord(30) + chord(18)) / 2 * slant, rel=1e-9)


def test_dlugi_dom_dzieli_sciany_zamiast_skalowac():
    pr = build_project(build_house(HouseParams(width=70, length=160, wall=60, roof=40)))
    walls = [pc for pc in pr.pieces if pc.part == 0]
    assert len(walls) > 1
    assert {pc.label for pc in walls} >= {"1a", "1b"}


@pytest.mark.parametrize("name", ["p51d", "bf109e"])
def test_samolot_szkielet_i_znaczniki(name):
    pr = build_project(REGISTRY[name][2](AircraftParams()))
    labels = {pl.label for pl in pr.model.plates}
    assert {"K", "WD", "Ż1P", "Ż1L"} <= labels
    # lewe i prawe skrzydło są lustrzane: te same pola, obrysy bez samoprzecięć (stary błąd „muszki”)
    by_name = {pr.model.mesh.parts[pc.part].name: pc for pc in pr.pieces}
    r, l = by_name["Skrzydło prawe 1"], by_name["Skrzydło lewe 1"]
    assert r.body.area == pytest.approx(l.body.area, rel=1e-6)
    # płaty są docięte do kadłuba: mają krawędź doklejenia z ząbkami, a kadłub — obrys i szczeliny
    assert any(e.vpart is not None and e.tabbed for e in r.boundary)
    styles = [st for pc in pr.pieces if pr.model.mesh.parts[pc.part].group == "fuselage" for st, _, _ in pc.marks]
    assert "glue" in styles and "cut" in styles
    assert not any("nasada" in pr.model.mesh.parts[pc.part].name for pc in pr.pieces)
    assert r.body.exterior.is_simple and l.body.exterior.is_simple
    wd = next(pl for pl in pr.model.plates if pl.label == "WD")
    assert len(wd.poly.exterior.coords) > 40 and wd.poly.is_valid


def test_stopien_trudnosci_zmienia_liczbe_czesci():
    counts = []
    for level in (1, 2, 3):
        pr = build_project(REGISTRY["bf109e"][2](AircraftParams(level=level)))
        counts.append(len(pr.items))
        assert bool(pr.model.plates) == (level > 1)
    assert counts[0] < counts[1] < counts[2]


def test_malowanie_lezy_na_czesciach():
    pr = build_project(REGISTRY["bf109e"][2](AircraftParams()))
    painted = 0
    for pc in pr.pieces:
        for pts, _, _ in pc.paint:
            g = Polygon(pts)
            painted += g.area
            assert g.buffer(-1e-3).within(pc.body.buffer(1e-3))   # farba nie wychodzi poza część
    assert painted > 1000
    # krzyże na kadłubie są po obu stronach, a więc na tym samym segmencie dwa razy
    black = [Polygon(pts).area for pc in pr.pieces if pr.model.mesh.parts[pc.part].group == "fuselage"
             for pts, col, alpha in pc.paint if col == "#141414" and alpha == 1]
    assert sum(black) > 50


# --- PDF ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def pdf_path(tmp_path_factory):
    pr = build_project(REGISTRY["bf109e"][2](AircraftParams()))
    path = tmp_path_factory.mktemp("pdf") / "arkusze.pdf"
    write_pdf(pr, path, validate(pr))
    return path, pr


def test_pdf_format_strony_i_polskie_znaki(pdf_path):
    from pypdf import PdfReader
    path, pr = pdf_path
    reader = PdfReader(str(path))
    w, h = PAGES[pr.page]
    for page in reader.pages:
        assert float(page.mediabox.width) == pytest.approx(w * 72 / 25.4, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(h * 72 / 25.4, abs=0.01)
    text = "".join(pg.extract_text() for pg in reader.pages[len(pr.sheets):])
    for word in ("Kolejność montażu", "Część", "Skrzydło", "Wręga", "Żebro", "dźwigarem", "Łopata śmigła"):
        assert word in text
    assert len(reader.pages) > len(pr.sheets)


def test_font_ma_polskie_znaki():
    from reportlab.pdfbase.ttfonts import TTFontFile
    face = TTFontFile(find_fonts()[0])
    assert all(ord(ch) in face.charToGlyph for ch in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")


@pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="brak pdftoppm")
def test_pasek_kontrolny_na_wydruku_ma_100_mm(pdf_path, tmp_path):
    path, pr = pdf_path
    dpi = 254  # 10 px na mm
    subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-f", "1", "-l", "1", str(path), str(tmp_path / "p")],
                   check=True)
    raw = next(tmp_path.glob("p*.pgm")).read_bytes()
    magic, w, h, _ = raw.split(maxsplit=4)[:4]
    assert magic == b"P5"
    w, h = int(w), int(h)
    img = np.frombuffer(raw[-w * h:], dtype=np.uint8).reshape(h, w)
    row = img[h - int(round((RULER_Y + 0.5) * 10))]
    dark = np.flatnonzero(row < 128)
    assert dark.size and dark[0] == pytest.approx(MARGIN * 10, abs=2)
    run = int(np.argmax(np.diff(dark) > 1)) + 1 if (np.diff(dark) > 1).any() else dark.size   # pierwszy ciągły odcinek
    assert run == pytest.approx(RULER_MM * 10, abs=2)


def test_rejestr_modeli_ma_domyslne_parametry():
    for name, (title, cls, build) in REGISTRY.items():
        assert build(cls()).mesh.faces, name


def test_dociecie_plata_lezy_na_powierzchni_kadluba():
    """Wierzchołki krawędzi doklejenia skrzydła leżą na poszyciu kadłuba (nie w powietrzu, nie w środku)."""
    pr = build_project(REGISTRY["bf109e"][2](AircraftParams()))
    mesh = pr.model.mesh
    fus = [fi for fi, f in enumerate(mesh.faces) if mesh.parts[f.part].group == "fuselage"]
    frames = [(mesh.face_frame(fi), Polygon(mesh.face_local(fi)).buffer(1e-3)) for fi in fus]
    from shapely.geometry import Point
    checked = 0
    for key, _ in mesh.attach.items():
        owner = mesh.faces[mesh.edges()[key][0][0]] if checked == 0 else None
        for i in key:
            p = mesh.V[i]
            if abs(p[1]) < 5 or not (50 < p[0] < 140):   # tylko okolica nasady skrzydła
                continue
            on = any(abs((p - o) @ n) < 1e-3 and poly.contains(Point((p - o) @ u, (p - o) @ v))
                     for (o, u, v, n), poly in frames)
            assert on
            checked += 1
        if checked > 40:
            break
    assert checked > 10


def test_szablony_kategorii_buduja_sie_i_przechodza_kontrole():
    from modelarz.szukaj import check
    for name in ("t34_rudy", "fiat126p"):
        import json
        from importlib import resources
        facts = json.loads((resources.files("modelarz.sceny") / f"{name}.json").read_text(encoding="utf-8"))
        assert check(facts) == []
    pr = build_project(REGISTRY["fiat126p"][2](REGISTRY["fiat126p"][1](wnetrze=1)))
    assert not [c.name for c in validate(pr) if not c.ok]
    assert any("Fotel" in pr.model.mesh.parts[pc.part].name for pc in pr.pieces)


def test_napisy_i_numery_poza_widoczna_powierzchnia():
    pr = build_project(REGISTRY["t34_rudy"][2](REGISTRY["t34_rudy"][1]()))
    texts = {t[2] for pc in pr.pieces for t in pc.paint_text}
    assert {"102", "RUDY"} <= texts
    from shapely.geometry import Point
    for pc in pr.pieces:
        assert not Point(pc.badge[0]).buffer(1.5).intersects(pc.body)      # numer części obok części
        for num, at in pc.seam_labels:                                     # numer szwu na zakładce albo za krawędzią
            assert not pc.body.buffer(-0.3).contains(Point(at))


def test_sprawdzenie_faktow_odrzuca_bzdury():
    from modelarz.szukaj import check
    bad = {"template": "czolg", "nazwa": "X", "dlugosc_kadluba": 6.1, "szerokosc": 3.0, "wysokosc_kadluba": 2.45,
           "wieza": {"x": 3, "dlugosc": 2, "szerokosc": 1.7, "wysokosc": 0.7}, "lufa": {"dlugosc": 3, "kaliber": 0.08},
           "kola": {"liczba": 5, "promien": 0.4}}
    assert check(bad)
    assert check({"template": "samochod", "nazwa": "Y"})


def test_obrys_z_rysunku_planu():
    """Syntetyczny plan: rzut boczny z linią ziemi i wymiarem oraz rzut z góry — ma wybrać boczny."""
    import cv2
    from modelarz.obrys import side_profile
    img = np.full((600, 900, 3), 255, np.uint8)
    side = np.array([[100, 250], [100, 170], [220, 150], [300, 80], [520, 80], [600, 160], [700, 170], [700, 250]], np.int32)
    cv2.polylines(img, [side], True, (0, 0, 0), 2)
    cv2.line(img, (40, 252), (860, 252), (0, 0, 0), 1)          # ziemia
    cv2.line(img, (100, 290), (700, 290), (0, 0, 0), 1)         # linia wymiarowa
    cv2.putText(img, "3000", (370, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.rectangle(img, (100, 340), (700, 560), (0, 0, 0), 2)    # rzut z góry (symetryczny)
    ok, png = cv2.imencode(".png", img)
    pts, preview = side_profile(png.tobytes(), 3.0, 0.85)
    assert pts and preview
    top = max(z for _, z in pts)
    assert top == pytest.approx(0.85, abs=0.02)
    z_at = lambda x: float(np.interp(x, [q[0] for q in pts], [q[1] for q in pts]))
    assert z_at(1.5) > 0.8                                       # dach
    assert z_at(0.3) < 0.55                                      # maska


def test_samochod_z_rzutow_planu_buduje_skorupe():
    """Sylwetka boczna + obrys z góry + rzut z przodu -> nadwozie z pasów podłużnych, wszystkie kontrole OK."""
    from modelarz.models import entry
    facts = {"template": "samochod", "nazwa": "Test", "dlugosc": 3.0, "szerokosc": 1.4, "wysokosc": 1.3,
             "rozstaw_osi": 1.8, "promien_kola": 0.26,
             "profil_gora": [[0, 0.6], [0.1, 0.75], [0.7, 0.82], [1.1, 1.28], [2.2, 1.3], [2.9, 0.7], [3.0, 0.5]],
             "obrys_gora": [[0, 0.5], [0.3, 0.68], [2.7, 0.68], [3.0, 0.5]],
             "obrys_przod": [[0.2, 0.68], [0.8, 0.68], [1.25, 0.5], [1.3, 0.45]]}
    title, cls, build = entry(facts)
    pr = build_project(build(cls()))
    assert not [f"{c.name}: {c.detail}" for c in validate(pr) if not c.ok]
    names = {pr.model.mesh.parts[pc.part].name for pc in pr.pieces}
    assert {"Bok prawy", "Okna prawe", "Maska, szyby i dach", "Podłoga", "Przód", "Tył"} <= names
    ys = [abs(v[1]) for v in pr.model.mesh.V]
    assert max(ys) == pytest.approx(0.68 * 1000 / cls().scale, rel=0.02)     # szerokość z rzutu z góry
