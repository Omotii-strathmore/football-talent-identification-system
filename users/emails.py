"""Branded Talanta Soka emails.

Every email is sent with a plain-text version (for old phones and spam filters) plus a styled
HTML version with the Talanta Soka header, a banner photo and a footer.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

BANNERS = {
    'player': 'email/banner-player.jpg',
    'team': 'email/banner-team.jpg',
    'welcome': 'email/banner-welcome.jpg',
}


def send_branded_email(subject, text_body, template, context, to, from_email=None, banner='player'):
    """Send `text_body` as plain text and `template` (under templates/emails/) as HTML."""
    site = settings.SITE_URL
    context = {
        'subject': subject,
        'site_url': site,
        'banner_url': f'{site}/static/{BANNERS.get(banner, BANNERS["player"])}',
        'support_email': settings.SUPPORT_EMAIL,
        **context,
    }
    html_body = render_to_string(f'emails/{template}', context)
    message = EmailMultiAlternatives(subject, text_body, from_email, to)
    message.attach_alternative(html_body, 'text/html')
    return message.send(fail_silently=False)


def send_welcome_email(user):
    """Sent once the account is verified. A failure here must never block the sign-in."""
    first_name = (user.full_name or '').split(' ')[0] or 'there'
    is_scout = user.role == 'scout'
    profile = getattr(user, 'player_profile', None) if not is_scout else None
    needs_guardian = bool(profile and profile.needs_guardian_approval)
    if is_scout:
        next_steps = [
            'Our team is reviewing your verification document. We will let you know once you are approved.',
            'Once approved, browse players by position, age and county.',
            'Post trials and tournaments so talented players can apply.',
        ]
    else:
        next_steps = [
            'Add a clear profile photo and complete your profile.',
            'Upload your best football videos: skills, goals, saves, and match moments.',
            'Check the trials page often and apply for opportunities near you.',
        ]
        if needs_guardian:
            next_steps.insert(0, 'Remind your parent or guardian to approve your account from the email we sent them.')
    text = (
        f'Hello {first_name},\n\n'
        'Your Talanta Soka account is verified. Karibu sana!\n\n'
        + ('Thank you for helping young Kenyan players get the chance they deserve.\n\n' if is_scout else
           'Every great player started somewhere, and today you took your first step. Keep training, keep believing.\n\n')
        + 'Your next steps:\n' + '\n'.join(f'- {s}' for s in next_steps)
        + f'\n\nSign in: {settings.SITE_URL}/login/\n\nNionekane nikicheza kwa TV!\nTalanta Soka'
    )
    try:
        send_branded_email(
            'Welcome to Talanta Soka! Your account is verified ✅', text, 'welcome.html',
            {'first_name': first_name, 'is_scout': is_scout, 'next_steps': next_steps,
             'login_url': f'{settings.SITE_URL}/login/'},
            [user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='welcome',
        )
        return True
    except Exception:
        logger.exception('Failed to send welcome email to %s', user.email)
        return False
