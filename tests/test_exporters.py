import pytest
from app.presets.demo_towers import get_demo_tower
from app.engine.analysis_service import TowerAnalysisService
from app.exporters.pdf_report import generate_pdf_report
from app.exporters.dxf_export import generate_dxf_geometry

def test_pdf_report_validity():
    t40 = get_demo_tower("40m")
    analysis = TowerAnalysisService.analyze(t40)
    pdf_bytes = generate_pdf_report(analysis, t40)
    
    # Must be valid non-empty PDF bytes starting with %PDF-
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-")

def test_dxf_export_validity():
    t40 = get_demo_tower("40m")
    analysis = TowerAnalysisService.analyze(t40)
    dxf_str = generate_dxf_geometry(analysis, t40)
    
    assert isinstance(dxf_str, str)
    assert len(dxf_str) > 1000
    assert "SECTION" in dxf_str
    assert "TOWER_LEGS" in dxf_str
    assert "TOWER_DIAGONALS" in dxf_str
    assert "ANTENNAS_EQUIPMENT" in dxf_str
    assert "EOF" in dxf_str
