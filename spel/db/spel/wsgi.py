"""
WSGI config for spel project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

import sys
from pathlib import Path

# like manage.py: the settings are `db.spel.settings`, importable with SPEL/spel on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'db.spel.settings')

application = get_wsgi_application()
