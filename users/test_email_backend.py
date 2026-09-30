import json
from unittest import mock

from django.core.mail import send_mail
from django.test import SimpleTestCase, override_settings


class _FakeResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(
    EMAIL_BACKEND='config.email_backends.BrevoEmailBackend',
    BREVO_API_KEY='test-key',
    BREVO_SENDER_EMAIL='sender@example.com',
    EMAIL_TIMEOUT=10,
)
class BrevoBackendTests(SimpleTestCase):
    def test_sends_through_brevo_api_with_verified_sender(self):
        with mock.patch('config.email_backends.urllib.request.urlopen', return_value=_FakeResponse()) as urlopen:
            sent = send_mail('Your code', 'Code is 123456', 'Talanta Soka <other@example.com>', ['player@example.com'])

        self.assertEqual(sent, 1)
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(request.get_header('Api-key'), 'test-key')
        body = json.loads(request.data)
        self.assertEqual(body['sender'], {'name': 'Talanta Soka', 'email': 'sender@example.com'})
        self.assertEqual(body['to'], [{'email': 'player@example.com'}])
        self.assertEqual(body['textContent'], 'Code is 123456')
        self.assertEqual(urlopen.call_args[1]['timeout'], 10)

    def test_failure_raises_unless_silent(self):
        with mock.patch('config.email_backends.urllib.request.urlopen', side_effect=OSError('network down')):
            with self.assertRaises(OSError):
                send_mail('s', 'b', None, ['player@example.com'])
            self.assertEqual(send_mail('s', 'b', None, ['player@example.com'], fail_silently=True), 0)
