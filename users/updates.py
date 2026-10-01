"""Emailing "What's new" updates to players and scouts.

When the administrator publishes an update, it is emailed in the background to every active,
non-staff user who has not unsubscribed. Brevo's free plan allows 300 emails a day, so update
emails stop at UPDATE_EMAILS_PER_DAY (leaving room for sign-up codes); anyone left over is emailed
the next time the administrator opens the Updates page.
"""
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.db import close_old_connections
from django.urls import reverse
from django.utils import timezone

from .emails import send_branded_email
from .models import SiteUpdate, UpdateReceipt, User

logger = logging.getLogger(__name__)

UNSUBSCRIBE_SALT = 'talanta-soka.updates-unsubscribe'
UPDATE_EMAILS_PER_DAY = 250


def unsubscribe_token(user):
    return signing.dumps({'u': user.pk}, salt=UNSUBSCRIBE_SALT)


def user_from_unsubscribe_token(token):
    try:
        data = signing.loads(token, salt=UNSUBSCRIBE_SALT)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=data.get('u')).first()


def recipients():
    """Verified (active), non-staff accounts that still want update emails."""
    return User.objects.filter(is_active=True, is_staff=False, updates_opt_out=False)


def emails_left_today():
    since = timezone.now() - timedelta(hours=24)
    return max(0, UPDATE_EMAILS_PER_DAY - UpdateReceipt.objects.filter(emailed_at__gte=since).count())


def update_link(update):
    return f'{settings.SITE_URL}/?update={update.pk}'


def send_update_email(update, user):
    first_name = (user.full_name or '').split(' ')[0] or 'there'
    points = update.point_list
    unsubscribe_url = settings.SITE_URL + reverse('updates_unsubscribe', args=[unsubscribe_token(user)])
    text = (
        f'Hello {first_name},\n\n{update.title}\n\n{update.teaser}\n\n'
        + ''.join(f'- {p}\n' for p in points)
        + f'\nSee what\'s new: {update_link(update)}\n\n'
        f'Do not want update emails? Unsubscribe: {unsubscribe_url}\n\nTalanta Soka'
    )
    send_branded_email(
        f'\U0001F195 What\'s New on Talanta Soka | {update.title}', text, 'update.html',
        {'first_name': first_name, 'update': update, 'points': points, 'link': update_link(update),
         'unsubscribe_url': unsubscribe_url},
        [user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='player',
    )
    receipt, _ = UpdateReceipt.objects.get_or_create(update=update, user=user)
    receipt.emailed_at = timezone.now()
    receipt.save(update_fields=['emailed_at'])


def queue_recipients(update):
    """Fix the list of people to email at the moment of publishing; people who join later are not emailed."""
    UpdateReceipt.objects.bulk_create(
        [UpdateReceipt(update=update, user=user) for user in recipients()],
        ignore_conflicts=True,
    )


def _waiting(update):
    return UpdateReceipt.objects.filter(
        update=update, emailed_at__isnull=True,
        user__is_active=True, user__is_staff=False, user__updates_opt_out=False,
    ).select_related('user').order_by('pk')


def send_pending(update):
    """Email everyone queued for this update who has not been emailed yet. Returns how many were sent."""
    sent = 0
    for receipt in _waiting(update)[:emails_left_today()]:
        try:
            send_update_email(update, receipt.user)
            sent += 1
        except Exception:
            logger.exception('Could not email update %s to %s', update.pk, receipt.user.email)
    return sent


def pending_count(update):
    return _waiting(update).count()


def _run(update_id):
    try:
        update = SiteUpdate.objects.filter(pk=update_id).first()
        if update:
            send_pending(update)
    finally:
        close_old_connections()


def send_in_background(update):
    """Send without making the administrator wait. Tests run it straight away instead."""
    if getattr(settings, 'UPDATE_EMAILS_IN_BACKGROUND', True):
        threading.Thread(target=_run, args=(update.pk,), daemon=True).start()
    else:
        send_pending(update)


def resume_unfinished():
    """Continue any update that could not reach everyone yet (for example after the daily limit)."""
    for update in SiteUpdate.objects.all()[:5]:
        if pending_count(update) and emails_left_today():
            send_in_background(update)
            break
