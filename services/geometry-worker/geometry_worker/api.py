"""FastAPI wrapper wokół pipeline CLI."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .cli import analyze_from_payload, generate_from_payload

app = FastAPI(title="Kartonowy Modelarz Geometry Worker", version="0.2.0")


class GenerateRequest(BaseModel):
    job_uuid: str
    shape: str = "box"
    parameters: dict = Field(default_factory=dict)
    output_dir: str


class AnalyzeRequest(BaseModel):
    image_path: str
    output_dir: str
    max_lines: int = 80


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "geometry-worker"}


@app.post("/v1/generate")
def generate(req: GenerateRequest) -> dict:
    return generate_from_payload(req.model_dump())


@app.post("/v1/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    return analyze_from_payload(req.model_dump())
