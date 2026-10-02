from django import template

from players.categories import SHORT, badge

register = template.Library()


@register.filter
def category_badge(category):
    """{{ profile.category|category_badge }} -> "Starlets" with its star emoji, or '' if not chosen."""
    return badge(category)


@register.filter
def category_name(category):
    return SHORT.get(category, '')
