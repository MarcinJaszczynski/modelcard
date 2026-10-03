"""Lekki interfejs w przeglądarce: wybór modelu, parametry, podgląd 3D i arkusze PDF."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlparse

from .cli import generate
from .models import REGISTRY

CACHE = Path(tempfile.gettempdir()) / "modelarz-web"

PAGE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>Modelarz</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{--bg:#f4f5f7;--panel:#fff;--ink:#1c2530;--mute:#667085;--line:#d9dde3;--acc:#1f5fbf;--ok:#16794a;--bad:#b42318}
  *{box-sizing:border-box} html,body{height:100%;margin:0}
  body{font:14px/1.4 system-ui,sans-serif;color:var(--ink);background:var(--bg);display:grid;grid-template-columns:300px 1fr}
  aside{background:var(--panel);border-right:1px solid var(--line);padding:16px;overflow:auto}
  h1{font-size:18px;margin:0 0 2px} .sub{color:var(--mute);font-size:12px;margin-bottom:14px}
  label{display:block;font-size:12px;color:var(--mute);margin:10px 0 3px}
  select,input{width:100%;padding:7px 8px;border:1px solid var(--line);border-radius:6px;font:inherit;background:#fff;color:var(--ink)}
  button{margin-top:14px;width:100%;padding:9px;border:0;border-radius:6px;background:var(--acc);color:#fff;font:inherit;font-weight:600;cursor:pointer}
  button:disabled{opacity:.6;cursor:wait}
  #checks{margin-top:16px;font-size:12px} #checks div{padding:5px 0;border-top:1px solid var(--line)}
  .ok b{color:var(--ok)} .bad b{color:var(--bad)} .err{color:var(--bad);margin-top:12px;font-size:13px}
  a.dl{display:block;margin-top:12px;color:var(--acc);font-weight:600}
  main{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);min-width:0}
  iframe{width:100%;height:100%;border:0;background:#fff}
  @media(max-width:900px){body{grid-template-columns:1fr;height:auto}main{grid-template-columns:1fr}iframe{height:70vh}}
</style></head><body>
<aside>
  <h1>Modelarz</h1><div class="sub">bryła 3D → rozwinięcia → arkusze 1:1</div>
  <label for="model">Model</label><select id="model"></select>
  <div id="params"></div>
  <label for="page">Arkusz</label><select id="page"><option>A4</option><option>A3</option></select>
  <button id="go">Generuj</button>
  <div id="out"></div><div id="checks"></div>
</aside>
<main><iframe id="view" title="Podgląd 3D"></iframe><iframe id="pdf" title="Arkusze PDF"></iframe></main>
<script>
const $ = id => document.getElementById(id);
let models = {};
function form() {
  const m = models[$('model').value];
  $('params').replaceChildren(...m.fields.flatMap(f => {
    const l = document.createElement('label'); l.textContent = f.label; l.htmlFor = 'p_' + f.name;
    const i = document.createElement('input'); i.type = 'number'; i.step = 'any'; i.id = 'p_' + f.name;
    i.value = f.default; if (f.min != null) i.min = f.min; if (f.max != null) i.max = f.max;
    return [l, i];
  }));
}
async function build() {
  const m = $('model').value, q = new URLSearchParams({model: m, page: $('page').value});
  for (const f of models[m].fields) q.set(f.name, $('p_' + f.name).value);
  $('go').disabled = true; $('go').textContent = 'Generuję…';
  try {
    const r = await (await fetch('/api/build?' + q)).json();
    $('checks').replaceChildren(); $('out').replaceChildren();
    if (r.error) { const e = document.createElement('div'); e.className = 'err'; e.textContent = r.error; $('out').append(e); return; }
    const s = document.createElement('div'); s.className = 'sub'; s.style.marginTop = '12px'; s.textContent = r.summary;
    const a = document.createElement('a'); a.className = 'dl'; a.href = r.pdf; a.download = m + '-arkusze.pdf'; a.textContent = 'Pobierz arkusze PDF';
    $('out').append(s, a);
    for (const c of r.checks) { const d = document.createElement('div'); d.className = c.ok ? 'ok' : 'bad';
      const b = document.createElement('b'); b.textContent = (c.ok ? '✓ ' : '✗ ') + c.name;
      d.append(b, document.createElement('br'), c.detail); $('checks').append(d); }
    $('view').src = r.preview; $('pdf').src = r.pdf + '#view=FitH';
  } finally { $('go').disabled = false; $('go').textContent = 'Generuj'; }
}
(async () => {
  models = await (await fetch('/api/models')).json();
  for (const [k, m] of Object.entries(models)) $('model').add(new Option(m.title, k));
  $('model').onchange = () => { form(); build(); }; $('go').onclick = build;
  form(); build();
})();
</script></body></html>
"""


def models_json() -> dict:
    out = {}
    for name, (title, cls, _) in REGISTRY.items():
        out[name] = {"title": title, "fields": [
            {"name": f.name, "label": f.metadata["label"], "default": f.default,
             "min": f.metadata.get("min"), "max": f.metadata.get("max")} for f in dataclasses.fields(cls)]}
    return out


def build(query: dict) -> dict:
    name, page = query.get("model", ""), query.get("page", "A4")
    if name not in REGISTRY or page not in ("A4", "A3"):
        return {"error": "Nieznany model lub format arkusza."}
    key = hashlib.sha1(json.dumps(sorted(query.items())).encode()).hexdigest()[:16]
    out = CACHE / key
    try:
        pr, checks = generate(name, query, page, out)
    except Exception as e:  # błąd parametrów albo część większa niż arkusz — pokazujemy użytkownikowi
        return {"error": str(e)}
    return {
        "summary": f"{pr.model.title}: {len(pr.pieces)} części poszycia, {len(pr.model.plates)} części szkieletu, "
                   f"{len(pr.sheets)} ark. {pr.page}",
        "checks": [dataclasses.asdict(c) for c in checks],
        "pdf": f"/files/{key}/arkusze.pdf", "preview": f"/files/{key}/podglad.html",
    }


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, ctype: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._send(PAGE.encode(), "text/html; charset=utf-8")
        if url.path == "/api/models":
            return self._send(json.dumps(models_json()).encode(), "application/json")
        if url.path == "/api/build":
            return self._send(json.dumps(build(dict(parse_qsl(url.query)))).encode(), "application/json")
        parts = url.path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "files" and parts[1].isalnum() and parts[2] in ("arkusze.pdf", "podglad.html"):
            f = CACHE / parts[1] / parts[2]
            if f.exists():
                ctype = "application/pdf" if f.suffix == ".pdf" else "text/html; charset=utf-8"
                return self._send(f.read_bytes(), ctype)
        self._send(b"404", "text/plain", 404)

    def log_message(self, *a):
        pass


def serve(port: int = 8791) -> None:
    print(f"Modelarz: http://127.0.0.1:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
