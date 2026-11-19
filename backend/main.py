"""Vercel / Production ASGI entrypoint."""
from app.main import create_app

app = create_app()

