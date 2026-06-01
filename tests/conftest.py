"""Pytest configuration: import paths and deps that load before test modules."""
import os
import sys


_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_backend_root = os.path.join(_project_root, "backend")

# Project root: `from backend.ai...` | Backend dir: `from ai...` (matches uvicorn cwd=backend).
for _p in (_project_root, _backend_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)


