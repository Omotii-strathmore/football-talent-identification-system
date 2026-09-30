"""Branded Talanta Soka emails.

Every email is sent with a plain-text version (for old phones and spam filters) plus a styled
HTML version with the Talanta Soka header, a banner photo and a footer.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

BANNERS = {
    'player': 'email/banner-player.jpg',
    'team': 'email/banner-team.jpg',
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
