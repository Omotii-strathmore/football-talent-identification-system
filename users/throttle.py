"""Stops people from guessing passwords and codes.

Each kind of attempt has a key (for example "login:amani@gmail.com"). After too many wrong tries
within a short window the key is locked for a while. The counts live in the database, so the limit
holds across every web server process.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import AuthThrottle

# name: (wrong tries allowed, within minutes, locked for minutes)
RULES = {
    'login': (5, 15, 15),        # per email address
    'login-ip': (20, 15, 15),    # per internet address, across all emails
    'code': (5, 15, 15),         # verification, reset and email-change codes, per account
}

LOCKED_MESSAGE = 'Too many wrong attempts. For your safety, please wait {minutes} minutes and try again.'


def _key(rule, value):
    return f'{rule}:{str(value).strip().lower()}'[:190]


def locked_minutes(rule, value):
    """Minutes left on a lock, or 0 if attempts are allowed."""
    row = AuthThrottle.objects.filter(key=_key(rule, value)).first()
    if row and row.locked_until and row.locked_until > timezone.now():
        return max(1, int((row.locked_until - timezone.now()).total_seconds() // 60) + 1)
    return 0


def record_failure(rule, value):
    """Count a wrong attempt. Returns True if this attempt caused a lock."""
    limit, window, lock = RULES[rule]
    now = timezone.now()
    with transaction.atomic():
        row, _ = AuthThrottle.objects.select_for_update().get_or_create(
            key=_key(rule, value), defaults={'window_start': now})
        if now - row.window_start > timedelta(minutes=window):
            row.failures, row.window_start, row.locked_until = 0, now, None
        row.failures += 1
        locked = row.failures >= limit
        if locked:
            row.locked_until = now + timedelta(minutes=lock)
            row.failures, row.window_start = 0, now
        row.save()
    return locked


def reset(rule, value):
    AuthThrottle.objects.filter(key=_key(rule, value)).delete()


def message(rule, value):
    return LOCKED_MESSAGE.format(minutes=locked_minutes(rule, value) or RULES[rule][2])


def client_ip(request):
    return request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')


RESEND_WAIT_SECONDS = 60


def resend_wait(user, purpose):
    """Seconds to wait before another code of this kind can be sent (stops email flooding)."""
    from .models import OneTimeCode
    last = OneTimeCode.objects.filter(user=user, purpose=purpose).order_by('-created_at').first()
    if not last:
        return 0
    passed = (timezone.now() - last.created_at).total_seconds()
    return max(0, int(RESEND_WAIT_SECONDS - passed))
