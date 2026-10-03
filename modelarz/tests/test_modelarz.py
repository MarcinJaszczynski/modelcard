"""Bramka jakości: arkusz ma wynikać z bryły i dać się skleić."""
import math
import shutil
import subprocess

import numpy as np
import pytest
from shapely.geometry import Polygon

from modelarz.layout import MARGIN, PAGES, PackError
from modelarz.models import REGISTRY, BoxParams, FrustumParams, HouseParams, P51Params
from modelarz.models import build_box, build_frustum, build_house, build_p51
from modelarz.pdf import RULER_MM, RULER_Y, find_fonts, write_pdf
from modelarz.preview import preview_data
from modelarz.project import build_project
from modelarz.validate import validate

CASES = {
    "pudelko": (build_box, BoxParams(), "A4"),
    "pudelko-plaskie": (build_box, BoxParams(width=150, depth=90, height=12), "A4"),
    "domek": (build_house, HouseParams(), "A4"),
    "domek-dlugi": (build_house, HouseParams(width=70, length=160, wall=60, roof=40), "A4"),
    "stozek-sciety": (build_frustum, FrustumParams(), "A4"),
    "walec": (build_frustum, FrustumParams(r_bottom=25, r_top=25, height=80), "A4"),
    "stozek": (build_frustum, FrustumParams(r_bottom=35, r_top=0, height=70, segments=16), "A4"),
    "p51-33": (build_p51, P51Params(), "A4"),
    "p51-48": (build_p51, P51Params(scale=48, dihedral=3), "A4"),
    "p51-24-a3": (build_p51, P51Params(scale=24), "A3"),
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
    assert all(len(v) == 2 for v in mesh.edges().values())
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
        if sm.length > 3.0:
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
    expected = sum(len(f.verts) - 2 for f in mesh.faces if not mesh.parts[f.part].virtual)
    assert tris == expected and data["seams"]


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


def test_p51_szkielet_i_znaczniki():
    pr = build_project(build_p51(P51Params()))
    labels = {pl.label for pl in pr.model.plates}
    assert {"K", "WD", "Ż1P", "Ż1L"} <= labels
    assert all(got == pytest.approx(exp, abs=1e-3) for got, exp in pr.mark_lengths)
    # lewe i prawe skrzydło są lustrzane: te same pola, obrysy bez samoprzecięć (stary błąd „muszki”)
    by_name = {pr.model.mesh.parts[pc.part].name: pc for pc in pr.pieces}
    r, l = by_name["Skrzydło prawe"], by_name["Skrzydło lewe"]
    assert r.body.area == pytest.approx(l.body.area, rel=1e-9)
    assert r.body.exterior.is_simple and l.body.exterior.is_simple
    # wręga z dźwigarem ma wpusty na kil i żebra
    wd = next(pl for pl in pr.model.plates if pl.label == "WD")
    assert len(wd.poly.exterior.coords) > 40 and wd.poly.is_valid


# --- PDF ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def pdf_path(tmp_path_factory):
    pr = build_project(build_p51(P51Params()))
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
    text = reader.pages[-1].extract_text()
    for word in ("Kolejność montażu", "Część", "Skrzydło", "Wręga", "Żebro", "dźwigarem"):
        assert word in text
    assert len(reader.pages) == len(pr.sheets) + 1


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
