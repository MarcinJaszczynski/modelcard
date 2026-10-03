import dataclasses
import json
from functools import partial
from importlib import resources
from pathlib import Path

from .aircraft import AircraftParams, build_aircraft
from .base import P
from .scene import build_scene
from .simple import BoxParams, FrustumParams, HouseParams, build_box, build_frustum, build_house
from .templates import TEMPLATES

USER_DIR = Path("modele")   # opisy utworzone przez wyszukiwanie (w katalogu roboczym)


def _scene_params(spec: dict):
    fields = [("scale", float, P("Skala 1:", float(spec.get("scale", 25)), 6, 1000)),
              ("level", int, P("Stopień trudności (1 łatwy – 3 trudny)", 2, 1, 3))]
    if spec.get("template") == "samochod":
        fields.append(("wnetrze", int, P("Wnętrze (0 nie, 1 tak)", 0, 0, 1)))
    fields += [("paper", float, P("Grubość kartonu poszycia [mm]", 0.25, 0.1, 0.6)),
               ("card", float, P("Grubość tektury [mm]", 1.0, 0.5, 2.0))]
    return dataclasses.make_dataclass("SceneParams", fields)


def _build_templated(spec: dict, p):
    scene = TEMPLATES[spec["template"]](spec, level=int(p.level), wnetrze=int(getattr(p, "wnetrze", 0)))
    return build_scene(scene, p)


def entry(spec: dict):
    """(tytuł, klasa parametrów, funkcja budująca) dla opisu z pliku."""
    if spec.get("template") == "samolot":
        air = TEMPLATES["samolot"](spec)
        return air["name"] + (f" {air['variant']}" if air.get("variant") else ""), AircraftParams, partial(build_aircraft, air)
    if "template" in spec:
        title = spec["nazwa"] + (f" {spec['wariant']}" if spec.get("wariant") else "")
        return title, _scene_params(spec), partial(_build_templated, spec)
    if "solids" in spec:
        return spec["name"], _scene_params(spec), partial(build_scene, spec)
    return spec["name"], AircraftParams, partial(build_aircraft, spec)


def load_registry() -> dict:
    reg = {
        "pudelko": ("Pudełko", BoxParams, build_box),
        "domek": ("Domek z dachem dwuspadowym", HouseParams, build_house),
        "walec": ("Walec / stożek ścięty", FrustumParams, build_frustum),
    }
    files = []
    for pkg in ("modelarz.samoloty", "modelarz.sceny"):
        files += [f for f in resources.files(pkg).iterdir() if f.name.endswith(".json")]
    if USER_DIR.is_dir():
        files += sorted(USER_DIR.glob("*.json"))
    for f in sorted(files, key=lambda q: q.name):
        reg[f.name[:-5]] = entry(json.loads(f.read_text(encoding="utf-8")))
    return reg


REGISTRY = load_registry()


def reload_registry() -> None:
    fresh = load_registry()
    REGISTRY.clear()
    REGISTRY.update(fresh)
