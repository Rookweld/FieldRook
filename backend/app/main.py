"""FieldRook API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import incidents, services

app = FastAPI(
    title="FieldRook API",
    version="0.1.0",
    description="Evidence-driven troubleshooting: Diagnose. Verify. Resolve.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(services.router)
app.include_router(incidents.router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"name": "FieldRook", "tagline": "Diagnose. Verify. Resolve."}
