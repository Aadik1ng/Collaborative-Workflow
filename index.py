"""Vercel serverless function entrypoint."""

from app.main import app

# Vercel looks for 'app' or 'handler' variable
__all__ = ["app"]
