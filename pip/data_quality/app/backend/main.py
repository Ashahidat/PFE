from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from config import FRONTEND_DIR
from routes import upload, dag, results, push_atlas

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(upload.router)
app.include_router(dag.router)
app.include_router(results.router)
app.include_router(push_atlas.router) 

# Frontend
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/ui")
def get_ui():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
