"""
Polymarket Edge Finder - API Server
===================================
FastAPI backend for the edge finding dashboard.

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from api import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app
app = FastAPI(
    title="Polymarket Edge Finder",
    description="Find trading edges in prediction markets",
    version="1.0.0"
)

# CORS - allow frontend to connect
# In production, replace "*" with your Netlify domain
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

# Check for environment variable to add production origin
import os
if os.environ.get("FRONTEND_URL"):
    ALLOWED_ORIGINS.append(os.environ.get("FRONTEND_URL"))

# For simplicity during development, allow all origins
# You can restrict this in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ALLOWED_ORIGINS for stricter security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "Polymarket Edge Finder API",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check for monitoring."""
    return {"status": "healthy"}
