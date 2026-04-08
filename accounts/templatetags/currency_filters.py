from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def inr(value):
    """Format a number in Indian currency format: 3,39,792.00"""
    try:
        d = Decimal(str(value))
        negative = d < 0
        if negative:
            d = -d

        integer_part, decimal_part = f"{d:.2f}".split(".")

        if len(integer_part) <= 3:
            grouped = integer_part
        else:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            parts = []
            while remaining:
                parts.insert(0, remaining[-2:] if len(remaining) >= 2 else remaining)
                remaining = remaining[:-2]
            grouped = ",".join(parts) + "," + last_three

        result = grouped + "." + decimal_part
        return ("-" + result) if negative else result
    except (ValueError, TypeError, InvalidOperation):
        return str(value) if value is not None else "0.00"
