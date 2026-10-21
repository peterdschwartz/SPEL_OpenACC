"""Django tests of the explorer: need the `db` extra and pytest-django; skipped otherwise."""

import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent  # spel/db
sys.path.insert(0, str(HERE.parent))  # so `db.app` imports as manage.py arranges it
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "db.spel.settings")
os.environ.setdefault("DJANGO_DEBUG", "true")
pytest.importorskip("django")
pytest.importorskip("pytest_django")
