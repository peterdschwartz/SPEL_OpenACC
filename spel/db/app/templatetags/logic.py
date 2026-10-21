from django import template

register = template.Library()


@register.filter
def lt(a, b):
    try:
        return int(a) < int(b)
    except Exception:
        return False


@register.filter
def lte(a, b):
    try:
        return int(a) <= int(b)
    except Exception:
        return False


@register.filter
def split(value, sep=","):
    return [v for v in str(value).split(sep) if v]
