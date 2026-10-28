"""
SynaptIQ server.

Serves:
  - /api/...   FastAPI routes (canvas app backends)
  - /          the static site (index.html, projects.html, synaptiq.html,
               style.css, Assets/, synaptiq_apps/) from the project root

Run from the `server/` directory:
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/ for the site,
http://localhost:8000/synaptiq.html for the canvas.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers import template_app

# Project root is one level up from this file (server/main.py -> project/)
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="SynaptIQ API")

# CORS is only needed if you serve the frontend separately (e.g. a live-server
# on a different port) instead of through this same FastAPI process. Since
# the canvas calls a relative "/api/..." path, same-origin serving needs none
# of this — but it's harmless to leave on for local dev flexibility.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API routes -------------------------------------------------------
# Register one router per canvas app. Each router owns its own path
# prefix, request/response models, and processing logic.
app.include_router(template_app.router, prefix="/api/template", tags=["template"])


@app.get("/api/health")
def health():
    return {"status": "ok"}


# --- Static site --------------------------------------------------------
# Mounted last so it acts as the catch-all for anything not matched by an
# /api/... route above (index.html, projects.html, synaptiq.html, style.css,
# Assets/, synaptiq_apps/, etc.). html=True lets "/" resolve to index.html.
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="site")
