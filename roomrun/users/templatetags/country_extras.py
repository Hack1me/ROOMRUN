from django import template

register = template.Library()


@register.filter
def country_flag(code: str) -> str:
    code = (code or "").upper().strip()
    if len(code) != 2:
        return ""
    try:
        return "".join(chr(ord(c) + 127397) for c in code)
    except TypeError:
        return ""
