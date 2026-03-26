"""
Shared pytest configuration.
Sets STATIC_DIR to the local static/ folder so FastAPI's StaticFiles mount
works when tests are run outside Docker.
"""
import os

# Must happen before any app module is imported.
os.environ.setdefault("STATIC_DIR", os.path.join(os.path.dirname(__file__), "..", "static"))
