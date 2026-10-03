"""Notifications for the administrator's dashboard."""
from django.urls import reverse

MILESTONE_STEP = 5


def notify_admins(kind, message, link=''):
    from .models import AdminNotification
    try:
        return AdminNotification.objects.create(kind=kind, message=message[:255], link=link[:200])
    except Exception:  # a notification must never break what the person was doing
        return None


def check_milestone(role):
    """Tell the admin each time the number of players or scouts reaches 5, 10, 15 ..."""
    from players.models import PlayerProfile
    from scouts.models import Scout
    count = PlayerProfile.objects.count() if role == 'player' else Scout.objects.count()
    if count and count % MILESTONE_STEP == 0:
        label = 'players' if role == 'player' else 'scouts'
        notify_admins('milestone', f'{count} {label} have now joined Talanta Soka!', reverse('admin_users'))
