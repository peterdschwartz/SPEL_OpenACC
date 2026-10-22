"""`{% static_v 'js/x.js' %}`: the static URL with the file's mtime as a query, so browsers refetch edited files."""

from __future__ import annotations

import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_v(path: str) -> str:
    url = static(path)
    found = finders.find(path)
    try:
        stamp = int(os.path.getmtime(found)) if found else 0
    except OSError:
        stamp = 0
    return f"{url}?v={stamp}" if stamp else url
