"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import filers, filings, securities

app = FastAPI(
    title="SecHub API",
    version="0.1.0",
    description="SEC filings about institutions, insiders, and funds.",
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
