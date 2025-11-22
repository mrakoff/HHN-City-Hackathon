from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .database import init_db
from .api import orders, drivers, locations, routes

# Initialize database
init_db()

app = FastAPI(title="Route Planning API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers FIRST (before static files)
app.include_router(orders.router)
app.include_router(drivers.router)
app.include_router(locations.router)
app.include_router(routes.router)

# Serve static files (frontend)
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "planner")
if os.path.exists(static_dir):
    @app.get("/")
    async def serve_index():
        """Serve index.html"""
        index_path = os.path.join(static_dir, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not found")

    @app.get("/app.js")
    async def serve_app_js():
        """Serve app.js"""
        file_path = os.path.join(static_dir, "app.js")
        if os.path.exists(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/styles.css")
    async def serve_styles_css():
        """Serve styles.css"""
        file_path = os.path.join(static_dir, "styles.css")
        if os.path.exists(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Not found")

    @app.get("/help.html")
    async def serve_help():
        """Serve help.html"""
        file_path = os.path.join(static_dir, "help.html")
        if os.path.exists(file_path):
            return FileResponse(file_path)
        raise HTTPException(status_code=404, detail="Not found")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Route Planning API is running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
