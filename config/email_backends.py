"""Send email through Brevo's HTTPS API.

Render's free web services cannot open outgoing SMTP connections, so Gmail SMTP hangs there.
Brevo's API works over normal HTTPS and needs only an API key and a verified sender address.
"""
import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            try:
                self._send(message)
                sent += 1
            except Exception:
                logger.exception('Brevo could not send email to %s', message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message):
        name, _ = parseaddr(message.from_email or '')
        payload = {
            # Brevo only sends from a verified sender, so always use it; keep the display name.
            'sender': {'name': name or getattr(settings, 'EMAIL_FROM_NAME', 'Talanta Soka'),
                       'email': settings.BREVO_SENDER_EMAIL},
            'to': [{'email': address} for address in message.to],
            'subject': message.subject,
            'textContent': message.body,
        }
        for content, mimetype in getattr(message, 'alternatives', []) or []:
            if mimetype == 'text/html':
                payload['htmlContent'] = content
        if message.cc:
            payload['cc'] = [{'email': address} for address in message.cc]
        if message.bcc:
            payload['bcc'] = [{'email': address} for address in message.bcc]
        if message.reply_to:
            payload['replyTo'] = {'email': message.reply_to[0]}

        request = urllib.request.Request(
            BREVO_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'api-key': settings.BREVO_API_KEY,
                'accept': 'application/json',
                'content-type': 'application/json',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:
                if response.status >= 300:
                    raise RuntimeError(f'Brevo returned HTTP {response.status}')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', 'ignore')[:300]
            raise RuntimeError(f'Brevo returned HTTP {exc.code}: {detail}') from exc
