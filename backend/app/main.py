"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import filers, filings, securities
from app.db import close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The pool opens lazily on first request (so the API can start before the DB
    # is reachable); close it cleanly on shutdown.
    yield
    close_pool()


app = FastAPI(
    title="SecHub API",
    version="0.1.0",
    description="SEC filings about institutions, insiders, and funds.",
    lifespan=lifespan,
)

# Local-first: the Next.js dev/prod frontend runs on :3000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(filers.router)
app.include_router(filings.router)
app.include_router(securities.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok"}
