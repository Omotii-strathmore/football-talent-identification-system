"""Parent/guardian approval for players under 18.

A player under 18 gives a parent's email at sign-up. The parent receives a link to a page where
they approve or decline. Until they approve, the player is hidden from scouts and cannot apply
for trials.
"""
import logging
from datetime import date

from django.conf import settings
from django.core import signing
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from users.emails import send_branded_email

logger = logging.getLogger(__name__)

TOKEN_SALT = 'talanta-soka.guardian-approval'
TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # the approval link works for 30 days
RESEND_WAIT_SECONDS = 120


def _adult_birthday_cutoff(today=None):
    """Anyone born on or before this date is 18 or older today."""
    today = today or date.today()
    try:
        return today.replace(year=today.year - 18)
    except ValueError:  # 29 February
        return today.replace(year=today.year - 18, day=28)


def visible_to_scouts_q(prefix=''):
    """Filter for player profiles scouts may see: adults, or minors whose guardian approved."""
    cutoff = _adult_birthday_cutoff()
    return (
        Q(**{prefix + 'date_of_birth__lte': cutoff})
        | Q(**{prefix + 'date_of_birth__isnull': True, prefix + 'age__gte': 18})
        | Q(**{prefix + 'guardian_approved_at__isnull': False})
    )


def make_token(profile):
    return signing.dumps({'p': profile.pk, 'e': profile.guardian_email.lower()}, salt=TOKEN_SALT)


def profile_from_token(token):
    """Return the profile for a valid link, or None if the link is invalid, expired or outdated."""
    from players.models import PlayerProfile

    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:
        return None
    profile = PlayerProfile.objects.filter(pk=data.get('p')).first()
    # A link stops working if the player later changed the guardian email.
    if not profile or profile.guardian_email.lower() != data.get('e'):
        return None
    return profile


def mask_email(email):
    name, _, domain = (email or '').partition('@')
    if not domain:
        return email
    return (name[:2] + '***@' + domain) if len(name) > 2 else (name[:1] + '***@' + domain)


def can_resend(profile):
    sent = profile.guardian_email_sent_at
    return not sent or (timezone.now() - sent).total_seconds() >= RESEND_WAIT_SECONDS


def send_guardian_email(request, profile):
    """Email the parent/guardian the approval link. Returns True if the email was sent."""
    if not profile.guardian_email:
        return False
    link = request.build_absolute_uri(reverse('guardian_review', args=[make_token(profile)]))
    guardian = profile.guardian_name or 'Parent or guardian'
    subject = f'👪 Parent Approval Needed | {profile.full_name} on Talanta Soka'
    message = (
        f'Hello {guardian},\n\n'
        f'{profile.full_name} (age {profile.age}) has signed up to Talanta Soka, a Kenyan platform that '
        'helps young footballers get seen by verified scouts from clubs and academies.\n\n'
        'Because they are under 18, we need your permission before scouts can see their profile '
        'and football videos, or before they can apply for trials.\n\n'
        'Please review and approve (or decline) here:\n'
        f'{link}\n\n'
        'What scouts would see: their name, age, county, playing position, profile photo and the '
        'football videos they upload. Scouts are checked by our team before they can see anyone, and '
        'they are never allowed to ask for money.\n\n'
        'If you did not expect this email, you can simply ignore it and the profile will stay hidden.\n\n'
        f'Questions? Write to us at {settings.SUPPORT_EMAIL}.\n\n'
        'Talanta Soka'
    )
    sender = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
    from_email = f"{getattr(settings, 'EMAIL_FROM_NAME', 'Talanta Soka')} <{sender}>" if sender else None
    try:
        send_branded_email(
            subject, message, 'guardian.html',
            {'link': link, 'guardian_name': guardian, 'player_name': profile.full_name, 'player_age': profile.age},
            [profile.guardian_email], from_email=from_email, banner='team',
        )
    except Exception:
        logger.exception('Failed to send guardian approval email for profile %s', profile.pk)
        return False
    profile.guardian_email_sent_at = timezone.now()
    profile.save(update_fields=['guardian_email_sent_at'])
    return True
