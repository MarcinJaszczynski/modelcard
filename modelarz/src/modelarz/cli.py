from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from .models import REGISTRY
from .pdf import write_pdf
from .preview import write_preview
from .project import Project, build_project
from .validate import Check, validate


def make_params(name: str, values: dict):
    cls = REGISTRY[name][1]
    kw = {}
    for f in dataclasses.fields(cls):
        if f.name in values and values[f.name] not in ("", None):
            v = type(f.default)(float(values[f.name]))
            lo, hi = f.metadata.get("min"), f.metadata.get("max")
            if (lo is not None and v < lo) or (hi is not None and v > hi):
                raise ValueError(f"{f.metadata['label']}: wartość {v:g} poza zakresem {lo:g}–{hi:g}")
            kw[f.name] = v
    return cls(**kw)


def generate(name: str, values: dict, page: str, out: Path) -> tuple[Project, list[Check]]:
    model = REGISTRY[name][2](make_params(name, values))
    pr = build_project(model, page)
    checks = validate(pr)
    out.mkdir(parents=True, exist_ok=True)
    write_pdf(pr, out / "arkusze.pdf", checks)
    write_preview(pr, out / "podglad.html")
    return pr, checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="modelarz", description="Projektowanie modeli kartonowych")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="generuje arkusze PDF i podgląd 3D")
    b.add_argument("model", choices=REGISTRY)
    b.add_argument("-o", "--out", default=None)
    b.add_argument("--page", choices=["A4", "A3"], default="A4")
    b.add_argument("--set", action="append", default=[], metavar="PARAMETR=WARTOŚĆ")
    s = sub.add_parser("serve", help="interfejs w przeglądarce")
    s.add_argument("--port", type=int, default=8791)
    sub.add_parser("list", help="lista modeli i parametrów")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for name, (title, cls, _) in REGISTRY.items():
            print(f"{name}: {title}")
            for f in dataclasses.fields(cls):
                print(f"    {f.name} = {f.default:g}   ({f.metadata['label']})")
        return 0
    if a.cmd == "serve":
        from .web import serve
        serve(a.port)
        return 0
    out = Path(a.out or f"out/{a.model}")
    pr, checks = generate(a.model, dict(kv.split("=", 1) for kv in a.set), a.page, out)
    print(f"{pr.model.title}: {len(pr.pieces)} części poszycia, {len(pr.model.plates)} części szkieletu, "
          f"{len(pr.sheets)} arkuszy {pr.page}")
    for ch in checks:
        print(f"  [{'OK' if ch.ok else 'BŁĄD'}] {ch.name}: {ch.detail}")
    print(f"-> {out / 'arkusze.pdf'}\n-> {out / 'podglad.html'}")
    return 0 if all(ch.ok for ch in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
