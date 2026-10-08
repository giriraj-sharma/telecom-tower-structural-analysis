import os
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.models.schemas import TowerInput, AnalysisOutput, OptimizationResponse
from app.presets.demo_towers import DEMO_CONFIGURATIONS, get_demo_tower
from app.engine.analysis_service import TowerAnalysisService
from app.engine.optimizer import TowerOptimizer
from app.exporters.pdf_report import generate_pdf_report
from app.exporters.dxf_export import generate_dxf_geometry

app = FastAPI(
    title="Telecom Tower Structural Analysis & Design Optimization",
    description="Educational / Preliminary Structural Analysis Tool for Telecom Lattice Towers (TIA-222 & Eurocode 3 Principles)",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "telecom-tower-structural-analysis",
        "version": "1.0.0",
        "notice": "Preliminary / Educational Tool Only - Not for certified structural construction"
    }

@app.get("/api/presets")
def get_presets():
    """
    Returns available demo tower configurations (30m, 40m, 50m)
    """
    return {
        "presets": [
            {
                "key": "30m",
                "name": "30m Light Urban Macro Tower",
                "tower_type": "3-leg",
                "height_m": 30.0,
                "description": "3-leg compact triangular lattice tower with light sector array and 0.6m microwave link (Urban Exposure B, 140 km/h wind)."
            },
            {
                "key": "40m",
                "name": "40m Standard Macro Site Tower",
                "tower_type": "4-leg",
                "height_m": 40.0,
                "description": "4-leg square lattice tower for standard multi-carrier cellular macro site with 2 microwave dishes (Open Exposure C, 160 km/h wind)."
            },
            {
                "key": "50m",
                "name": "50m Heavy Rural / Coastal Backbone Tower",
                "tower_type": "4-leg",
                "height_m": 50.0,
                "description": "Heavy-duty 4-leg lattice tower for coastal/mountain backbone transmission with multiple 1.8m dishes (Coastal Exposure D, 185 km/h wind)."
            }
        ]
    }

@app.get("/api/presets/{key}", response_model=TowerInput)
def get_preset_detail(key: str):
    if key not in DEMO_CONFIGURATIONS:
        raise HTTPException(status_code=404, detail=f"Preset configuration '{key}' not found. Available: 30m, 40m, 50m")
    return get_demo_tower(key)

@app.post("/api/analyze", response_model=AnalysisOutput)
def analyze_tower(params: TowerInput):
    """
    Executes dead load, wind load, base shear, overturning moment, deflection, 
    member capacity (Euler/AISC column buckling), and load combination analysis.
    """
    try:
        return TowerAnalysisService.analyze(params)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis calculation error: {str(e)}")

@app.post("/api/optimize", response_model=OptimizationResponse)
def optimize_tower(params: TowerInput):
    """
    Performs parametric multi-candidate design comparison and Pareto-cost optimization.
    """
    try:
        baseline = TowerAnalysisService.analyze(params)
        optimizer = TowerOptimizer(params)
        return optimizer.run_optimization(baseline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization error: {str(e)}")

@app.post("/api/export/pdf")
def export_pdf_report(params: TowerInput):
    """
    Generates downloadable formal PDF engineering calculation book report.
    """
    try:
        analysis = TowerAnalysisService.analyze(params)
        pdf_bytes = generate_pdf_report(analysis, params)
        filename = f"Tower_Report_{params.height_m:.0f}m_{params.tower_type}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

@app.post("/api/export/dxf")
def export_dxf_cad(params: TowerInput):
    """
    Generates downloadable AutoCAD-compatible 3D DXF wireframe file with layers.
    """
    try:
        analysis = TowerAnalysisService.analyze(params)
        dxf_str = generate_dxf_geometry(analysis, params)
        filename = f"Tower_CAD_{params.height_m:.0f}m_{params.tower_type}.dxf"
        return Response(
            content=dxf_str.encode("utf-8"),
            media_type="application/dxf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DXF CAD export error: {str(e)}")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))
