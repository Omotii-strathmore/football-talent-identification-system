"""Trial-day reminders: on the day of a trial, each shortlisted player gets one "Today is the day" email.

Render's free plan has no scheduled jobs, so the first visit to the site each day sends that day's reminders
(see config.middleware.DailyTasksMiddleware). Each reminder is claimed in the database before sending,
so a player never gets two, even if several visits arrive at once.
"""
import logging
import threading

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from users.emails import send_branded_email

from .models import Application

logger = logging.getLogger(__name__)
_last_run = {'day': None}


def todays_trials(day=None):
    day = day or timezone.localdate()
    return (Application.objects.select_related('opportunity', 'player')
            .filter(status='shortlisted', reminder_sent_at__isnull=True, player__is_active=True)
            .filter(Q(opportunity__event_date=day) | Q(opportunity__event_date__isnull=True, opportunity__deadline=day)))


def send_trial_day_reminders(day=None):
    day = day or timezone.localdate()
    sent = 0
    for application in todays_trials(day):
        # Claim it first: only one process can turn reminder_sent_at from empty to now.
        if not Application.objects.filter(pk=application.pk, reminder_sent_at__isnull=True).update(reminder_sent_at=timezone.now()):
            continue
        user, opp = application.player, application.opportunity
        first_name = (user.full_name or '').split(' ')[0] or 'there'
        text = (f'Hello {first_name},\n\nToday is the day! You were shortlisted for {opp.title} by {opp.organization}.\n'
                f'Where: {opp.location}\n\nBring boots, shin guards and water, and arrive early: don\'t be late.\n\n'
                f'All the best!\nTalanta Soka')
        try:
            send_branded_email(
                f'\U0001F929 Today is the day! Don\'t be late, {first_name}', text, 'trial_day.html',
                {'first_name': first_name, 'title': opp.title, 'organization': opp.organization, 'location': opp.location,
                 'day': day.strftime('%A %d %B'), 'link': settings.SITE_URL + reverse('my_applications')},
                [user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='player',
            )
            sent += 1
        except Exception:
            logger.exception('Trial-day reminder failed for application %s', application.pk)
    return sent


def run_once_today():
    """Called on visits: sends today's reminders the first time each day (per server process)."""
    today = timezone.localdate()
    if _last_run['day'] == today:
        return
    _last_run['day'] = today
    if getattr(settings, 'TRIAL_REMINDERS_IN_BACKGROUND', True):
        threading.Thread(target=send_trial_day_reminders, args=(today,), daemon=True).start()
    else:
        send_trial_day_reminders(today)
