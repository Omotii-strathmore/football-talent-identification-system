"""Badges that reward effort and character. Only positive: there are no negative marks and no rankings.

Players earn five automatically (Ready to be Scouted, Highlight Reel, First Step, Good Listener, Pioneer) and one from
verified scouts (Fair Play). Scouts earn Helpful Scout by giving feedback to many players.
"""
from datetime import date

from django.conf import settings

HELPFUL_SCOUT_PLAYERS = 10
GOOD_LISTENER_REPLIES = 3

PLAYER_BADGES = [
    ('ready', '✅', 'Ready to be Scouted', 'Add a profile photo, your position, a short bio and at least one video.'),
    ('reel', '\U0001F3A5', 'Highlight Reel', 'Upload 3 videos so scouts can see more of your game.'),
    ('first_step', '\U0001F680', 'First Step', 'Apply to your first trial.'),
    ('listener', '\U0001F4AC', 'Good Listener', "Reply to scouts' feedback on your videos 3 times."),
    ('pioneer', '\U0001F331', 'Pioneer', 'For players who joined Talanta Soka in its first season.'),
    ('fair_play', '\U0001F91D', 'Fair Play', 'Given by verified scouts for respect, teamwork and discipline.'),
]


def pioneer_until():
    value = getattr(settings, 'PIONEER_UNTIL', '2026-12-31')
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return date(2026, 12, 31)


def is_pioneer(user):
    joined = getattr(user, 'terms_accepted_at', None)
    # Accounts made before join dates were recorded are among the very first members.
    return joined is None or joined.date() <= pioneer_until()


def player_badges(profile, video_count=None, application_count=None, awards=None, reply_count=None):
    """Every player badge with `earned` set, so a player's own dashboard can show how to earn the rest."""
    if video_count is None:
        video_count = profile.videos.count()
    if application_count is None:
        application_count = profile.user.opportunity_applications.count()
    if reply_count is None:
        from scouts.models import ScoutVideoFeedback
        reply_count = ScoutVideoFeedback.objects.filter(video__profile=profile).exclude(player_reply='').count()
    if awards is None:
        awards = list(profile.fair_play_awards.select_related('scout').all())
    earned = {
        'ready': bool(profile.profile_photo and profile.position and (profile.bio or '').strip() and video_count >= 1),
        'reel': video_count >= 3,
        'first_step': application_count >= 1,
        'listener': reply_count >= GOOD_LISTENER_REPLIES,
        'pioneer': is_pioneer(profile.user),
        'fair_play': bool(awards),
    }
    detail = {}
    if awards:
        counts = {}
        for award in awards:
            for label in award.quality_labels:
                counts[label] = counts.get(label, 0) + 1
        top = sorted(counts, key=lambda label: -counts[label])[:3]
        detail['fair_play'] = ' · '.join(part for part in [f'×{len(awards)}' if len(awards) > 1 else '', ', '.join(top)] if part)
    return [
        {'key': key, 'emoji': emoji, 'name': name, 'hint': hint, 'earned': earned[key], 'detail': detail.get(key, '')}
        for key, emoji, name, hint in PLAYER_BADGES
    ]


def players_helped(scout_user):
    """How many different players this scout has given feedback to."""
    from scouts.models import ScoutPlayerFeedback, ScoutVideoFeedback
    ids = set(ScoutPlayerFeedback.objects.filter(scout=scout_user).values_list('profile_id', flat=True))
    ids |= set(ScoutVideoFeedback.objects.filter(scout=scout_user).values_list('video__profile_id', flat=True))
    return len(ids)


def scout_badges(scout_user):
    helped = players_helped(scout_user)
    return [{
        'key': 'helpful', 'emoji': '\U0001F64C', 'name': 'Helpful Scout', 'earned': helped >= HELPFUL_SCOUT_PLAYERS,
        'hint': f'Give feedback to {HELPFUL_SCOUT_PLAYERS} players.',
        'detail': '', 'progress': min(helped, HELPFUL_SCOUT_PLAYERS), 'goal': HELPFUL_SCOUT_PLAYERS,
    }]


def can_award_fair_play(scout_user, profile):
    """Only scouts who have actually dealt with the player: in their Interests, given feedback, or applied to their trial."""
    from opportunities.models import Application
    from scouts.models import ScoutPlayerFeedback, ScoutPlayerShortlist, ScoutVideoFeedback
    return (
        ScoutPlayerShortlist.objects.filter(scout=scout_user, profile=profile).exists()
        or ScoutPlayerFeedback.objects.filter(scout=scout_user, profile=profile).exists()
        or ScoutVideoFeedback.objects.filter(scout=scout_user, video__profile=profile).exists()
        or Application.objects.filter(player=profile.user, opportunity__scout=scout_user).exists()
    )
