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
        return dictionary.get(key)
    
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
