"""Changing and verifying emails from the profile page.

Login email: the person types a new email, we send a code to it, and only when the code is entered
does the login email change (the old one keeps working until then, and is told about the change).

Contact email (players): the email scouts may use to reach a player. It shows as "Verified" once the
player enters a code sent to it; scouts only ever see verified contact emails.
"""
import random
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import throttle
from .email_check import check_email
from .emails import send_code_email, send_security_alert
from .models import OneTimeCode, User

CODE_MINUTES = 15


class EmailChangeError(Exception):
    """A message that is safe to show the user."""


def _send_code(user, purpose, to_email):
    wait = throttle.resend_wait(user, purpose)
    if wait:
        raise EmailChangeError(f'A code was sent a moment ago. Check your inbox and Spam, or try again in {wait} seconds.')
    OneTimeCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)
    code = f'{random.randint(0, 999999):06d}'
    OneTimeCode.objects.create(user=user, code=code, method='email', purpose=purpose, target_email=to_email,
                               expires_at=timezone.now() + timedelta(minutes=CODE_MINUTES))
    try:
        send_code_email(user, code, purpose, to_email)
    except Exception:
        raise EmailChangeError('We could not send the code right now. Please try again in a few minutes.')


def start_login_email_change(user, new_email):
    new_email = (new_email or '').strip().lower()
    if new_email == user.email.lower():
        raise EmailChangeError('That is already your login email.')
    new_email, problem, suggestion = check_email(new_email)
    if problem:
        raise EmailChangeError(problem)
    user.pending_email = new_email
    user.save(update_fields=['pending_email'])
    _send_code(user, 'newemail', new_email)


def resend_login_email_code(user):
    if not user.pending_email:
        raise EmailChangeError('There is no new email waiting to be verified.')
    _send_code(user, 'newemail', user.pending_email)


def cancel_login_email_change(user):
    user.pending_email = ''
    user.save(update_fields=['pending_email'])
    OneTimeCode.objects.filter(user=user, purpose='newemail', used=False).update(used=True)


def start_contact_verification(user, profile):
    email = (profile.contact_email or '').strip().lower()
    if not email:
        raise EmailChangeError('Add a contact email first, then verify it.')
    _send_code(user, 'contact', email)


def _check_code(user, purpose, code, target):
    if throttle.locked_minutes('code', user.pk):
        raise EmailChangeError(throttle.message('code', user.pk))
    otp = (OneTimeCode.objects.filter(user=user, purpose=purpose, used=False, code=(code or '').strip(),
                                      target_email__iexact=target).order_by('-created_at').first())
    if not otp:
        if throttle.record_failure('code', user.pk):
            OneTimeCode.objects.filter(user=user, purpose=purpose, used=False).update(used=True)
            raise EmailChangeError(throttle.message('code', user.pk) + ' Then send a new code.')
        raise EmailChangeError('That code is not right. Check the latest email from us and try again.')
    if otp.expires_at and otp.expires_at < timezone.now():
        raise EmailChangeError('That code has expired. Send a new one.')
    otp.used = True
    otp.save(update_fields=['used'])
    throttle.reset('code', user.pk)


def confirm_login_email(user, code):
    if not user.pending_email:
        raise EmailChangeError('There is no new email waiting to be verified.')
    new_email = user.pending_email
    _check_code(user, 'newemail', code, new_email)
    with transaction.atomic():
        if User.objects.filter(email__iexact=new_email).exclude(pk=user.pk).exists():
            raise EmailChangeError('Another account started using that email. Please choose a different one.')
        old_email = user.email
        user.email = new_email
        user.pending_email = ''
        user.save(update_fields=['email', 'pending_email'])
    # A contact email that matches the newly verified login email is verified too.
    profile = getattr(user, 'player_profile', None)
    if profile and (profile.contact_email or '').strip().lower() == new_email and not profile.contact_email_verified_at:
        profile.contact_email_verified_at = timezone.now()
        profile.save(update_fields=['contact_email_verified_at'])
    send_security_alert(user, 'email', new_email=new_email, to_email=old_email)
    return old_email


def confirm_contact_email(user, profile, code):
    email = (profile.contact_email or '').strip().lower()
    _check_code(user, 'contact', code, email)
    profile.contact_email_verified_at = timezone.now()
    profile.save(update_fields=['contact_email_verified_at'])


def contact_email_changed(profile, old_email):
    """Call when a player saves their profile: a new contact email must be verified again."""
    new = (profile.contact_email or '').strip().lower()
    if new == (old_email or '').strip().lower():
        return
    if new and new == profile.user.email.lower():
        profile.contact_email_verified_at = timezone.now()   # same as the verified login email
    else:
        profile.contact_email_verified_at = None
    profile.save(update_fields=['contact_email_verified_at'])
