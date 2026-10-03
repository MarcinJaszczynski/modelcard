"""Podgląd 3D bryły (three.js) jako samodzielny plik HTML."""
from __future__ import annotations

import json

from .project import Project

TEMPLATE = """<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><title>__TITLE__</title>
<style>
  html,body{margin:0;height:100%;background:#eef1f4;font:13px system-ui,sans-serif;color:#1c2530;overflow:hidden}
  #bar{position:absolute;left:10px;top:10px;background:#ffffffd9;padding:6px 10px;border-radius:6px}
  #bar label{margin-right:10px}
</style></head><body>
<div id="bar"><b>__TITLE__</b><br>
<label><input type="checkbox" id="skin" checked> poszycie</label>
<label><input type="checkbox" id="edges" checked> szwy</label>
<label><input type="checkbox" id="plates" checked> szkielet</label></div>
<script type="importmap">{"imports":{"three":"https://unpkg.com/three@0.160.0/build/three.module.js",
"three/addons/":"https://unpkg.com/three@0.160.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
const D = __DATA__;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xeef1f4);
const cam = new THREE.PerspectiveCamera(35, innerWidth/innerHeight, 1, 20000);
cam.up.set(0,0,1);
const r = new THREE.WebGLRenderer({antialias:true});
r.setPixelRatio(devicePixelRatio); r.setSize(innerWidth, innerHeight); document.body.appendChild(r.domElement);
scene.add(new THREE.HemisphereLight(0xffffff, 0x8899aa, 1.6));
const sun = new THREE.DirectionalLight(0xffffff, 1.4); sun.position.set(-1,-2,3); scene.add(sun);
const skin = new THREE.Group(), edges = new THREE.Group(), plates = new THREE.Group();
scene.add(skin, edges, plates);
for (const m of D.meshes) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(m.pos, 3));
  g.computeVertexNormals();
  skin.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({color:m.color, flatShading:true,
    side:THREE.DoubleSide, roughness:.85, polygonOffset:true, polygonOffsetFactor:1, polygonOffsetUnits:1})));
}
const line = (pts, color, grp) => { const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
  grp.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({color}))); };
line(D.seams, 0x222222, edges);
line(D.plates, 0xb45309, plates);
const box = new THREE.Box3().setFromObject(skin), c = box.getCenter(new THREE.Vector3());
const size = box.getSize(new THREE.Vector3()).length();
cam.position.set(c.x - size*.9, c.y - size*1.1, c.z + size*.7);
const ctl = new OrbitControls(cam, r.domElement); ctl.target.copy(c); ctl.update();
for (const [id, grp] of [['skin',skin],['edges',edges],['plates',plates]])
  document.getElementById(id).onchange = e => { grp.visible = e.target.checked; draw(); };
const draw = () => r.render(scene, cam);
ctl.addEventListener('change', draw);
addEventListener('resize', () => { cam.aspect = innerWidth/innerHeight; cam.updateProjectionMatrix();
  r.setSize(innerWidth, innerHeight); draw(); });
draw();
</script></body></html>
"""


def preview_data(pr: Project) -> dict:
    mesh = pr.model.mesh
    by_color: dict = {}
    for fi, f in enumerate(mesh.faces):
        part = mesh.parts[f.part]
        if part.virtual:
            continue
        p = mesh.face_points(fi)
        buf = by_color.setdefault(f.color or part.color, [])
        for i in range(1, len(p) - 1):
            for q in (p[0], p[i], p[i + 1]):
                buf.extend(round(float(x), 3) for x in q)
    seams = []
    for pc in pr.pieces:
        for be in pc.boundary:
            for i in be.key:
                seams.extend(round(float(x), 3) for x in mesh.V[i])
    plates = []
    for pl in pr.model.plates:
        pts = pl.to3d(list(pl.poly.exterior.coords))
        for a, b in zip(pts, pts[1:]):
            plates.extend(round(float(x), 3) for q in (a, b) for x in q)
    return {"meshes": [{"color": c, "pos": v} for c, v in by_color.items()], "seams": seams, "plates": plates}


def write_preview(pr: Project, path) -> None:
    html = TEMPLATE.replace("__TITLE__", pr.model.title).replace("__DATA__", json.dumps(preview_data(pr)))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(html)
