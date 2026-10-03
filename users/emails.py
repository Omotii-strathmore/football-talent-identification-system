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
    'reset': 'email/banner-reset.jpg',
    'coach': 'email/banner-coach-tall.jpg',
    'coach_group': 'email/banner-coach-group.jpg',
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
        + f'\n\nSign in: {settings.SITE_URL}/login/\n\n'
        'Mungu akubariki in every match.\n\nNionekane nikicheza kwa TV!\nTalanta Soka'
    )
    try:
        send_branded_email(
            '🎉 Welcome to Talanta Soka! Account Verified ✅', text, 'welcome.html',
            {'first_name': first_name, 'is_scout': is_scout, 'next_steps': next_steps,
             'login_url': f'{settings.SITE_URL}/login/'},
            [user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='welcome',
        )
        return True
    except Exception:
        logger.exception('Failed to send welcome email to %s', user.email)
        return False


def send_scout_decision_email(scout, approved, reason=''):
    """Tell a scout the result of the document review. A failure here must never block the admin."""
    user = scout.user
    first_name = (user.full_name or '').split(' ')[0] or 'there'
    site = settings.SITE_URL
    if approved:
        subject = "🔭 You're Verified, Coach! Start Discovering Talent ✅"
        link = f'{site}/login/'
        text = (
            f'Hello {first_name},\n\n'
            f'Good news: your documents have been approved and your scout account for {scout.organization} is verified.\n\n'
            'You can now:\n'
            '- Browse players by position, age and county\n'
            '- Watch their videos and give feedback\n'
            '- Save players to your Interests list\n'
            '- Post trials and tournaments\n\n'
            'Please remember: never ask players for money, and contact players under 18 only through the platform '
            'or with a parent present.\n\n'
            f'Start scouting: {link}\n\nTalanta Soka'
        )
        template, banner = 'scout_approved.html', 'coach'
    else:
        subject = '⚠️ Action Needed | Scout Documents Not Verified'
        link = f'{site}/login/?next=/scout/verification/resubmit/'
        text = (
            f'Hello {first_name},\n\n'
            'Thank you for applying to scout on Talanta Soka. Unfortunately we could not verify the documents you sent.\n\n'
            + (f'Reason from our team: {reason}\n\n' if reason else '')
            + 'This is not the end. Upload a clear coaching licence, club letter or accreditation and we will review it again.\n\n'
            f'Try again: {link}\n\n'
            f'Questions? Write to us at {settings.SUPPORT_EMAIL}.\n\nTalanta Soka'
        )
        template, banner = 'scout_rejected.html', 'coach_group'
    try:
        send_branded_email(
            subject, text, template,
            {'first_name': first_name, 'organization': scout.organization, 'reason': reason, 'link': link,
             'scouts_for': getattr(scout, 'scouts_for', 'both')},
            [user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner=banner,
        )
        return True
    except Exception:
        logger.exception('Failed to send scout decision email to %s', user.email)
        return False


def send_security_alert(user, kind, new_email='', to_email=None):
    """Tell someone their password or login email changed, in case it was not them."""
    from django.utils import timezone
    from players.guardian import mask_email

    first_name = (user.full_name or '').split(' ')[0] or 'there'
    when = timezone.localtime().strftime('%d %B %Y at %H:%M')
    if kind == 'password':
        subject = '\U0001F6E1️ Your Talanta Soka Password Was Changed'
        text = f'Hello {first_name},\n\nYour Talanta Soka password was changed on {when}.\n\nNot you? Write to {settings.SUPPORT_EMAIL} straight away.\n\nTalanta Soka'
    else:
        subject = '\U0001F6E1️ Your Talanta Soka Login Email Was Changed'
        text = (f'Hello {first_name},\n\nOn {when} the email you use to log in to Talanta Soka was changed to {mask_email(new_email)}.\n\n'
                f'Not you? Write to {settings.SUPPORT_EMAIL} straight away.\n\nTalanta Soka')
    try:
        send_branded_email(
            subject, text, 'security_alert.html',
            {'first_name': first_name, 'kind': kind, 'when': when, 'new_email_masked': mask_email(new_email)},
            [to_email or user.email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='team',
        )
        return True
    except Exception:
        logger.exception('Failed to send security alert to %s', to_email or user.email)
        return False


def send_code_email(user, code, purpose, to_email):
    """Email a 6-digit code to an address the user wants to start using."""
    subject = '\U0001F511 Confirm Your Email | Talanta Soka'
    text = f'Hello {user.full_name},\n\nYour Talanta Soka confirmation code is: {code}\nIt expires in 15 minutes.\n\nIf you did not ask for this, ignore this email.'
    send_branded_email(
        subject, text, 'code.html',
        {'code': code, 'purpose': purpose, 'full_name': user.full_name, 'first_name': (user.full_name or '').split(' ')[0]},
        [to_email], from_email=f'{settings.EMAIL_FROM_NAME} <{settings.DEFAULT_FROM_EMAIL}>', banner='player',
    )
