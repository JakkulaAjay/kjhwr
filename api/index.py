"""Vercel serverless entrypoint: exposes the FastAPI ASGI app."""
from backend.app.main import app  # noqa: F401
