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
from . import szukaj
from .models import REGISTRY, USER_DIR, reload_registry

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
  textarea{width:100%;padding:7px 8px;border:1px solid var(--line);border-radius:6px;font:inherit}
  button.sec{background:#fff;color:var(--acc);border:1px solid var(--acc);margin-top:8px}
  #src{grid-column:1/-1;background:var(--panel);padding:18px 22px;overflow:auto}
  #src h2{font-size:16px;margin:0 0 4px} #src h3{font-size:13px;margin:18px 0 8px;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
  .card{border:1px solid var(--line);border-radius:8px;padding:6px;font-size:11px;display:flex;flex-direction:column;gap:4px;cursor:pointer}
  .card img{width:100%;height:120px;object-fit:contain;background:#f4f5f7;border-radius:4px}
  .card.off{opacity:.35} .card input,.web input{width:auto;margin-right:6px}
  .web{display:block;font-size:12px;margin:5px 0;color:var(--ink)} .web a{color:var(--acc)}
  #src .bar{display:flex;gap:10px;align-items:center;margin-top:18px;position:sticky;bottom:0;background:var(--panel);padding:10px 0}
  #src .bar input{flex:1} #src .bar button{width:auto;margin:0;padding:9px 18px}
  @media(max-width:900px){body{grid-template-columns:1fr;height:auto}main{grid-template-columns:1fr}iframe{height:70vh}}
</style></head><body>
<aside>
  <h1>Modelarz</h1><div class="sub">bryła 3D → rozwinięcia → arkusze 1:1</div>
  <label for="q">Nowy model z nazwy</label>
  <input id="q" placeholder="np. T-34 Czterej pancerni, Polski Fiat 126p">
  <button id="find" class="sec">Szukaj planów i danych</button>
  <label for="model">Model</label><select id="model"></select>
  <div id="params"></div>
  <label for="page">Arkusz</label><select id="page"><option>A4</option><option>A3</option></select>
  <button id="go">Generuj</button>
  <div id="out"></div>
  <div id="fix" hidden><label for="uwagi">Co poprawić w tym modelu?</label>
    <textarea id="uwagi" rows="3" placeholder="np. wieża za niska, kolor ciemniejszy, numer 102 większy"></textarea>
    <button id="revise" class="sec">Popraw model</button></div>
  <div id="checks"></div>
</aside>
<main><section id="src" hidden></section><iframe id="view" title="Podgląd 3D"></iframe><iframe id="pdf" title="Arkusze PDF"></iframe></main>
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
    if (r.outline) { const i = document.createElement('img'); i.src = r.outline; i.alt = 'Obrys odczytany z planu';
      i.style.cssText = 'width:100%;margin-top:10px;border:1px solid var(--line);border-radius:6px';
      const c = document.createElement('div'); c.className = 'sub'; c.textContent = 'Obrys odczytany z planu (czerwona linia)';
      $('out').append(i, c); }
    for (const c of r.checks) { const d = document.createElement('div'); d.className = c.ok ? 'ok' : 'bad';
      const b = document.createElement('b'); b.textContent = (c.ok ? '✓ ' : '✗ ') + c.name;
      d.append(b, document.createElement('br'), c.detail); $('checks').append(d); }
    $('view').src = r.preview; $('pdf').src = r.pdf + '#view=FitH';
  } finally { $('go').disabled = false; $('go').textContent = 'Generuj'; }
}
async function loadModels(select) {
  models = await (await fetch('/api/models')).json();
  $('model').replaceChildren();
  for (const [k, m] of Object.entries(models)) $('model').add(new Option((m.user ? '★ ' : '') + m.title, k));
  if (select) $('model').value = select;
  $('fix').hidden = !models[$('model').value].user;
  form();
}
function el(tag, props, ...kids) { const e = Object.assign(document.createElement(tag), props || {}); e.append(...kids); return e; }
let found = null;
async function search() {
  const q = $('q').value.trim(); if (!q) return;
  $('find').disabled = true; $('find').textContent = 'Szukam w sieci…';
  try {
    found = await (await fetch('/api/search?q=' + encodeURIComponent(q))).json();
    const box = $('src'); box.replaceChildren(); box.hidden = false; $('view').hidden = $('pdf').hidden = true;
    if (found.error) { box.append(el('div', {className: 'err', textContent: found.error})); return; }
    box.append(el('h2', {textContent: 'Źródła do akceptacji: ' + found.plan.obiekt + (found.plan.kontekst ? ' — ' + found.plan.kontekst : '')}),
      el('div', {className: 'sub', textContent: 'Odznacz to, co nie pasuje. Zaznaczone dane i rysunki posłużą do zbudowania modelu.'}));
    if (found.article) box.append(el('h3', {textContent: 'Artykuł'}), el('a', {className: 'web', href: found.article.url, target: '_blank', textContent: found.article.title}));
    if (found.web.length) box.append(el('h3', {textContent: 'Strony z danymi'}));
    found.web.forEach((w, i) => { const c = el('input', {type: 'checkbox', checked: true}); c.dataset.web = i;
      box.append(el('label', {className: 'web'}, c, el('a', {href: w.url, target: '_blank', textContent: w.title}), ' — ' + w.snippet.slice(0, 140))); });
    for (const group of [...new Set(found.images.map(i => i.group))]) {
      const grid = el('div', {className: 'grid'});
      found.images.forEach((im, i) => { if (im.group !== group) return;
        const c = el('input', {type: 'checkbox', checked: true}); c.dataset.img = i;
        const card = el('label', {className: 'card'}, el('img', {src: im.thumb, alt: im.title, loading: 'lazy'}), el('span', {}, c, im.title.slice(0, 70)),
          el('a', {href: im.page, target: '_blank', textContent: 'źródło'}));
        c.onchange = () => card.classList.toggle('off', !c.checked); grid.append(card); });
      box.append(el('h3', {textContent: group}), grid);
    }
    const opts = el('input', {id: 'opts', placeholder: 'Życzenia: wariant, malowanie, z wnętrzem / bez…'});
    const go = el('button', {textContent: 'Akceptuję — buduj model'});
    go.onclick = () => create(go);
    box.append(el('div', {className: 'bar'}, opts, go));
  } finally { $('find').disabled = false; $('find').textContent = 'Szukaj planów i danych'; }
}
async function create(btn) {
  const skip = [...document.querySelectorAll('#src input[data-img]')].filter(c => !c.checked).map(c => c.dataset.img);
  const skipweb = [...document.querySelectorAll('#src input[data-web]')].filter(c => !c.checked).map(c => c.dataset.web);
  btn.disabled = true; btn.textContent = 'Buduję model (lokalna AI, ok. 1–2 min)…';
  const q = new URLSearchParams({id: found.id, opts: $('opts').value, skip: skip.join(','), skipweb: skipweb.join(',')});
  const r = await (await fetch('/api/create?' + q)).json();
  btn.disabled = false; btn.textContent = 'Akceptuję — buduj model';
  if (r.error) { $('src').append(el('div', {className: 'err', textContent: r.error})); return; }
  $('src').hidden = true; $('view').hidden = $('pdf').hidden = false;
  await loadModels(r.name); build();
}
async function revise() {
  const t = $('uwagi').value.trim(); if (!t) return;
  $('revise').disabled = true; $('revise').textContent = 'Poprawiam…';
  const r = await (await fetch('/api/revise?' + new URLSearchParams({name: $('model').value, uwagi: t}))).json();
  $('revise').disabled = false; $('revise').textContent = 'Popraw model';
  if (r.error) { $('out').replaceChildren(el('div', {className: 'err', textContent: r.error})); return; }
  $('uwagi').value = ''; await loadModels($('model').value); build();
}
(async () => {
  await loadModels();
  $('model').onchange = () => { $('fix').hidden = !models[$('model').value].user; form(); build(); };
  $('go').onclick = build; $('find').onclick = search; $('revise').onclick = revise;
  $('q').onkeydown = e => { if (e.key === 'Enter') search(); };
  build();
})();
</script></body></html>
"""


def models_json() -> dict:
    out = {}
    for name, (title, cls, _) in REGISTRY.items():
        out[name] = {"title": title, "user": (USER_DIR / f"{name}.json").exists(), "fields": [
            {"name": f.name, "label": f.metadata["label"], "default": f.default,
             "min": f.metadata.get("min"), "max": f.metadata.get("max")} for f in dataclasses.fields(cls)]}
    return out


def build(query: dict) -> dict:
    name, page = query.get("model", ""), query.get("page", "A4")
    if name not in REGISTRY or page not in ("A4", "A3"):
        return {"error": "Nieznany model lub format arkusza."}
    user = USER_DIR / f"{name}.json"
    stamp = user.read_text(encoding="utf-8") if user.exists() else ""
    key = hashlib.sha1((json.dumps(sorted(query.items())) + stamp).encode()).hexdigest()[:16]
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
        "outline": f"/obrys/{name}.png" if (USER_DIR / f"{name}_obrys.png").exists() else None,
    }


FOUND: dict = {}


def api_search(query: dict) -> dict:
    try:
        src = szukaj.find_sources(query.get("q", ""))
    except Exception as e:
        return {"error": f"Wyszukiwanie nie powiodło się: {e}"}
    src["id"] = hashlib.sha1(src["query"].encode()).hexdigest()[:12]
    FOUND[src["id"]] = src
    art = src["article"]
    return {**src, "article": {"title": art["title"], "url": art["url"]} if art else None}


def api_create(query: dict) -> dict:
    src = FOUND.get(query.get("id", ""))
    if not src:
        return {"error": "Najpierw wyszukaj źródła."}
    for key, field in (("skip", "images"), ("skipweb", "web")):
        off = {int(i) for i in query.get(key, "").split(",") if i.isdigit()}
        for i, item in enumerate(src[field]):
            item["accepted"] = i not in off
    try:
        name, facts, problems = szukaj.create(src["query"], src, query.get("opts", ""))
    except Exception as e:
        return {"error": str(e)}
    if problems or not name:
        return {"error": "Nie udało się ułożyć poprawnego modelu: " + "; ".join(problems)}
    reload_registry()
    return {"name": name}


def api_revise(query: dict) -> dict:
    try:
        _, problems = szukaj.revise(query.get("name", ""), query.get("uwagi", ""))
    except Exception as e:
        return {"error": str(e)}
    if problems:
        return {"error": "Poprawka odrzucona: " + "; ".join(problems)}
    reload_registry()
    return {"ok": True}


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
        for path, fn in (("/api/search", api_search), ("/api/create", api_create), ("/api/revise", api_revise)):
            if url.path == path:
                return self._send(json.dumps(fn(dict(parse_qsl(url.query)))).encode(), "application/json")
        if url.path == "/api/build":
            return self._send(json.dumps(build(dict(parse_qsl(url.query)))).encode(), "application/json")
        parts = url.path.strip("/").split("/")
        if len(parts) == 2 and parts[0] == "obrys" and parts[1].endswith(".png") and parts[1][:-4].replace("_", "").isalnum():
            f = USER_DIR / f"{parts[1][:-4]}_obrys.png"
            if f.exists():
                return self._send(f.read_bytes(), "image/png")
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
