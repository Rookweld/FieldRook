"""FieldRook API entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import actions, collector_import, incidents, investigations, knowledge, resolutions, services
from .security import LocalOriginMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from .investigations import persistence

    stuck = persistence.fail_stuck_executions()
    if stuck:
        print(f"FieldRook: marked {stuck} interrupted action(s) as failed.")
    yield


app = FastAPI(
    title="FieldRook API",
    version="0.3.0",
    description="Evidence-driven troubleshooting: Diagnose. Verify. Resolve.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(LocalOriginMiddleware)

app.include_router(services.router)
app.include_router(incidents.router)
app.include_router(investigations.router)
app.include_router(actions.router)
app.include_router(collector_import.router)
app.include_router(resolutions.router)
app.include_router(knowledge.router)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"name": "FieldRook", "tagline": "Diagnose. Verify. Resolve."}
