"""Checks that an email address can really receive our verification code.

We cannot prove an inbox exists without emailing it (that is what the verification code does), but
we can catch most mistakes before sign-up: bad format, common domain typos such as "gmial.com",
throwaway "disposable" inboxes, domains that cannot receive email at all, and addresses that
already have an account.
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import User

# Common misspellings of popular email domains in Kenya.
DOMAIN_TYPOS = {
    'gmial.com': 'gmail.com', 'gmai.com': 'gmail.com', 'gmal.com': 'gmail.com', 'gamil.com': 'gmail.com',
    'gnail.com': 'gmail.com', 'gmail.co': 'gmail.com', 'gmail.con': 'gmail.com', 'gmail.cm': 'gmail.com',
    'gmaill.com': 'gmail.com', 'gmail.om': 'gmail.com', 'gmeil.com': 'gmail.com', 'gimail.com': 'gmail.com',
    'yahoo.co': 'yahoo.com', 'yaho.com': 'yahoo.com', 'yahooo.com': 'yahoo.com', 'yahoo.con': 'yahoo.com',
    'hotmail.co': 'hotmail.com', 'hotmal.com': 'hotmail.com', 'hotmial.com': 'hotmail.com', 'hotmail.con': 'hotmail.com',
    'outlook.co': 'outlook.com', 'outlok.com': 'outlook.com', 'outlook.con': 'outlook.com',
    'icloud.co': 'icloud.com', 'iclod.com': 'icloud.com',
    'strathmore.ac.ke.com': 'strathmore.edu', 'strathmore.com': 'strathmore.edu',
}

# Throwaway inboxes that delete themselves; accounts on them cannot be reached later.
DISPOSABLE_DOMAINS = {
    'mailinator.com', 'guerrillamail.com', 'guerrillamail.net', 'sharklasers.com', '10minutemail.com',
    'tempmail.com', 'temp-mail.org', 'tempmail.net', 'yopmail.com', 'trashmail.com', 'getnada.com',
    'dispostable.com', 'maildrop.cc', 'throwawaymail.com', 'fakeinbox.com', 'mohmal.com', 'emailondeck.com',
    'mintemail.com', 'mytemp.email', 'tempinbox.com', 'spamgourmet.com', 'moakt.com', 'burnermail.io',
}

# Domains we know accept email; skips the internet lookup for the most common ones.
KNOWN_GOOD = {'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'icloud.com', 'live.com', 'strathmore.edu', 'ymail.com', 'proton.me', 'protonmail.com'}


def domain_accepts_email(domain):
    """True if the domain has mail servers (or an address). Unknown when the lookup itself fails."""
    if domain in KNOWN_GOOD:
        return True
    try:
        import dns.exception
        import dns.resolver
    except ImportError:
        return True
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 3.0
    try:
        resolver.resolve(domain, 'MX')
        return True
    except (dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False
    except dns.resolver.NoAnswer:
        # No mail servers listed; mail can still go to the domain's own address.
        try:
            resolver.resolve(domain, 'A')
            return True
        except Exception:
            return False
    except (dns.exception.Timeout, Exception):
        # Our own internet hiccup should never block a real person; the verification code still checks.
        return True


def unfinished_signup(email):
    """An account that stopped after sign-up step 1: never verified and no player or scout profile.

    No code was ever sent to it, so whoever signs up again with this email simply starts over.
    """
    user = User.objects.filter(email__iexact=(email or '').strip(), is_active=False, is_staff=False).first()
    if user and not hasattr(user, 'player_profile') and not hasattr(user, 'scout_profile'):
        return user
    return None


def check_email(email, check_dns=None):
    """Return (cleaned_email, problem, suggestion). `problem` is None when the email can be used."""
    if check_dns is None:
        check_dns = getattr(settings, 'EMAIL_DNS_CHECK', True)
    email = (email or '').strip().lower()
    if not email:
        return email, 'Please enter your email address.', None
    try:
        validate_email(email)
    except ValidationError:
        return email, 'This does not look like an email address. Check it, for example name@gmail.com.', None

    local, _, domain = email.rpartition('@')
    if domain in DOMAIN_TYPOS:
        fixed = f'{local}@{DOMAIN_TYPOS[domain]}'
        return email, f'Did you mean {fixed}?', fixed
    if domain in DISPOSABLE_DOMAINS:
        return email, 'Temporary email addresses cannot be used. Please use an email you will keep, such as Gmail.', None
    if not re.search(r'\.[a-z]{2,}$', domain):
        return email, 'The part after @ looks incomplete, for example gmail.com.', None
    if User.objects.filter(email__iexact=email).exists() and not unfinished_signup(email):
        return email, 'This email already has a Talanta Soka account. Log in, or reset your password if you forgot it.', None
    if check_dns and not domain_accepts_email(domain):
        return email, f'"{domain}" cannot receive emails, so your verification code would never arrive. Please check the spelling.', None
    return email, None, None
