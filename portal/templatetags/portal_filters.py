"""
Custom template filters for portal app.
"""
from django import template

register = template.Library()


@register.filter
def dict_get(dictionary, key):
    """
    Safely get a value from a dictionary using a key.
    Usage in template: {{ my_dict|dict_get:key }}
    
    This handles nested dict access for the matrix view where we need:
    matrix_data[employee_id][date] to get status
    """
    if dictionary is None:
        return None
    
    if isinstance(dictionary, dict):
        val = dictionary.get(key)
        if val is None and key is not None:
             # Try converting key to string (handles UUID vs str mismatch)
             str_key = str(key)
             val = dictionary.get(str_key)
             # DEBUG PRINT
             if "fp_summary_stats" in str(dictionary) or len(str(dictionary)) > 20: # Heuristic to detect stats dict
                 # Only print if we are likely looking at stats to avoid spam
                 pass 
                 # print(f"DEBUG: dict_get key={key} (type={type(key)}) -> str_key={str_key} -> val={val}")
        return val
    
    return None


@register.filter
def get_status_class(status):
    """
    Return CSS class for status cell.
    Usage in template: {{ status|get_status_class }}
    """
    status_classes = {
        'H': 'status-H',
        'A': 'status-A',
        'S': 'status-S',
        'I': 'status-I',
        'L': 'status-L',
        '': 'status-empty',
    }
    return status_classes.get(status, 'status-empty')


@register.filter
def is_sunday(date_obj):
    """
    Check if a date is Sunday (weekday == 6).
    Usage in template: {% if d|is_sunday %}...{% endif %}
    """
    if date_obj is None:
        return False
    try:
        return date_obj.weekday() == 6
    except AttributeError:
        return False
