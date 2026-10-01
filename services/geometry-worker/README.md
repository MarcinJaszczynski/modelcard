# Geometry Worker

Deterministyczny silnik rozwinięć kartonowych.

## CLI

```bash
python3 -m geometry_worker generate --input request.json
```

### request.json

```json
{
  "job_uuid": "uuid",
  "shape": "box",
  "parameters": {
    "width_mm": 80,
    "height_mm": 50,
    "depth_mm": 40,
    "flap_mm": 8,
    "sheet": "A4"
  },
  "output_dir": "/tmp/out"
}
```

### response (stdout)

```json
{
  "ok": true,
  "svg_path": "/tmp/out/sheet.svg",
  "parts": [{"id": "1", "name": "front", "label": "1 PRZÓD"}],
  "instructions": ["..."],
  "sheet": {"format": "A4", "width_mm": 210, "height_mm": 297}
}
```

## FastAPI

```bash
pip install -r requirements.txt
uvicorn geometry_worker.api:app --port 8090
# POST /v1/generate  — ten sam payload
# GET  /health
```
