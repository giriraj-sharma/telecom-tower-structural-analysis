import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.presets.demo_towers import get_demo_tower

client = TestClient(app)

def test_health_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "telecom-tower-structural-analysis" in data["service"]

def test_get_presets_list():
    res = client.get("/api/presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert len(data["presets"]) >= 3
    keys = [p["key"] for p in data["presets"]]
    assert "30m" in keys and "40m" in keys and "50m" in keys

def test_get_preset_detail():
    res = client.get("/api/presets/40m")
    assert res.status_code == 200
    data = res.json()
    assert data["height_m"] == 40.0
    assert data["tower_type"] == "4-leg"

def test_analyze_endpoint():
    t40 = get_demo_tower("40m").model_dump()
    res = client.post("/api/analyze", json=t40)
    assert res.status_code == 200
    data = res.json()
    assert "overall_status" in data
    assert "max_utilization" in data
    assert "governing_load_combination" in data
    assert "base_shear_kn" in data
    assert "overturning_moment_knm" in data
    assert "intermediate_calculations" in data
    assert len(data["load_combinations"]) >= 5
    assert len(data["nodes"]) > 0
    assert len(data["members"]) > 0

def test_optimize_endpoint():
    t40 = get_demo_tower("40m").model_dump()
    res = client.post("/api/optimize", json=t40)
    assert res.status_code == 200
    data = res.json()
    assert "baseline_configuration" in data
    assert "recommended_configuration" in data
    assert "candidates" in data
    assert len(data["candidates"]) >= 5

def test_export_pdf_endpoint():
    t40 = get_demo_tower("40m").model_dump()
    res = client.post("/api/export/pdf", json=t40)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert len(res.content) > 1000

def test_export_dxf_endpoint():
    t40 = get_demo_tower("40m").model_dump()
    res = client.post("/api/export/dxf", json=t40)
    assert res.status_code == 200
    assert "application/dxf" in res.headers["content-type"]
    assert b"SECTION" in res.content
