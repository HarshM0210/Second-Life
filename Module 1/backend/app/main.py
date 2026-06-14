"""
Second Life Commerce — Module 1: Grading, Fraud Detection & Quality System.

FastAPI application entry point with CORS middleware for React frontend.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.database import init_db
from app.routers.returns import router as returns_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Second Life Commerce — Grading & Quality System",
    description="Module 1: AI-powered grading, fraud detection, and disposition routing for returned items.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for React frontend (dev: localhost:5173, production: configure as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "module": "grading-fraud-quality"}


# Register routers
app.include_router(returns_router)
