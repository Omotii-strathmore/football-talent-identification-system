"""Stars and Starlets: Talanta Soka's two football categories.

Stars are players in men's football and Starlets are players in women's football, after Kenya's
national teams, the Harambee Stars and the Harambee Starlets. The category is used only to match
players with the right scouts and trials.
"""
STARS = 'stars'
STARLETS = 'starlets'
OPEN = 'open'
BOTH = 'both'

PLAYER_CATEGORY_CHOICES = [
    (STARS, "Stars (men's football)"),
    (STARLETS, "Starlets (women's football)"),
]
SCOUTS_FOR_CHOICES = [
    (BOTH, 'Stars and Starlets'),
    (STARS, "Stars (men's football)"),
    (STARLETS, "Starlets (women's football)"),
]
OPPORTUNITY_CATEGORY_CHOICES = [
    (OPEN, 'Open to all'),
    (STARS, "Stars (men's football)"),
    (STARLETS, "Starlets (women's football)"),
]

EMOJI = {STARS: '⭐', STARLETS: '\U0001F31F', OPEN: '⚽', BOTH: '⭐\U0001F31F'}
SHORT = {STARS: 'Stars', STARLETS: 'Starlets', OPEN: 'Open to all', BOTH: 'Stars & Starlets'}


def badge(category):
    """Short label with its emoji, e.g. "Starlets" with a glowing star."""
    if category not in SHORT:
        return ''
    return f'{EMOJI[category]} {SHORT[category]}'


def can_apply(player_category, opportunity_category):
    """Players apply to trials for their own category, or ones open to all."""
    return opportunity_category in (OPEN, '', None) or opportunity_category == player_category
