from django import template
from django.contrib.auth import get_user_model


register = template.Library()


@register.filter
def subtract(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''


@register.filter(name='abs')
def abs_filter(value):
    try:
        return abs(value)
    except Exception:
        return value
    

@register.filter
def username(user_id):
    if user_id:
        User = get_user_model()
        try:
            user = User.objects.get(pk=user_id)
            return user.username
        except User.DoesNotExist:
            return ''
    return ''


@register.filter
def dict_get(d, key):
    return d.get(key)


@register.filter
def due_status(transaction, current_date):
    if transaction.status.lower() != "confirmed":
        if (current_date - transaction.created_at).days >= 7:
            return "Yes"
    return ""