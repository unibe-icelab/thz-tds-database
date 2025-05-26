
# spectra/templatetags/spectra_extras.py
from django import template
import pprint

register = template.Library()

@register.filter
def is_list(value):
    return isinstance(value, list)

@register.filter
def is_dict(value):
    return isinstance(value, dict)

@register.filter
def pprint(value):
    try:
        return pprint.pformat(value, indent=2, width=60) # Adjust width as needed
    except Exception:
        return str(value) # Fallback
