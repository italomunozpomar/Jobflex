from django import template
from django.utils import timezone
from datetime import datetime, date, timedelta
import locale

register = template.Library()

@register.filter(name='format_clp')
def format_clp(value):
    """
    Formats a number as a string with dots for thousands separators (CLP format).
    Example: 1000000 -> "1.000.000"
    """
    try:
        # Tries to set the locale to Chilean Spanish, which uses dots for thousands.
        # This is more robust than using a German locale.
        try:
            locale.setlocale(locale.LC_ALL, 'es_CL.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'es_CL')
            except locale.Error:
                # Fallback to the system's default locale if Chilean Spanish is not available
                locale.setlocale(locale.LC_ALL, '') 
        
        # Format the number with grouping (thousands separators)
        return locale.format_string("%d", int(value), grouping=True)
    except (ValueError, TypeError, locale.Error):
        # If any error occurs (e.g., value is not a number, or all locales fail),
        # return the original value as a fallback.
        return value

@register.filter
def custom_timesince(value):
    if not value:
        return ""

    now = timezone.now()
    
    # Ensure value is a datetime object
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    
    # Make sure the datetime is timezone-aware if it's not already
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_default_timezone())

    diff = now - value

    if diff < timedelta(minutes=60):
        return "< 1 hora"
    elif diff < timedelta(hours=24):
        hours = diff.seconds // 3600
        if hours == 0: # Handle cases just under 1 hour but caught by the 60-min check
            return "< 1 hora"
        return f"{hours} hora{'s' if hours != 1 else ''}"
    elif diff < timedelta(days=30):
        days = diff.days
        return f"{days} día{'s' if days != 1 else ''}"
    else:
        months = diff.days // 30
        if months < 12:
            return f"{months} mes{'es' if months != 1 else ''}"
        else:
            years = months // 12
            return f"{years} año{'s' if years != 1 else ''}"
