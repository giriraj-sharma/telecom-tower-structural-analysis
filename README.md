# Telecom Tower Structural Analysis

A preliminary analysis workstation for telecom lattice towers. It combines a FastAPI calculation API with an interactive browser interface for tower inputs, structural checks, 3D geometry, design comparisons, and file exports.

> **Engineering notice:** Educational and preliminary-use tool only. Results are not certified for construction. Have assumptions, loads, and designs verified by a licensed structural engineer against applicable standards.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. The interactive API documentation is at `/docs`; the health check is at `/health`.

## Test

```bash
python -m pytest -q
```

## Main features

- 30 m, 40 m, and 50 m sample tower configurations, with editable geometry, steel, wind, and equipment inputs
- Wind and dead-load calculations, member capacity checks, serviceability, load combinations, and 3D model output
- Candidate design optimization with estimated cost and steel mass comparisons
- PDF calculation report and DXF geometry exports

## Deploy

The app is compatible with Vercel's FastAPI runtime. Install the Vercel CLI, authenticate, and run:

```bash
vercel --prod
```

The `app/main.py` FastAPI application serves the interface and API from the same deployment.
