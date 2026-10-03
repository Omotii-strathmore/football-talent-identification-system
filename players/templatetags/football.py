from django import template

from players.categories import SHORT, badge, person_badge

register = template.Library()


@register.filter
def category_badge(category):
    """{{ profile.category|category_badge }} -> "Starlets" with its star emoji, or '' if not chosen."""
    return badge(category)


@register.filter
def category_person(category):
    """{{ profile.category|category_person }} -> "Star" or "Starlet" with its emoji (one player)."""
    return person_badge(category)


@register.filter
def category_name(category):
    return SHORT.get(category, '')
