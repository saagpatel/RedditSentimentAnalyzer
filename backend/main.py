"""FastAPI application — serves sentiment data and mounts API routes."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import posts, sentiment, spikes
from backend.config import configure_logging, get_config
from backend.db.connection import deploy_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging()
    deploy_schema()
    yield


app = FastAPI(
    title="Reddit Sentiment Analyzer",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(sentiment.router)
app.include_router(posts.router)
app.include_router(spikes.router)


@app.get("/health")
async def health() -> dict:
    config = get_config()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "tracked_subreddits": config.ingestion.subreddits,
    }
