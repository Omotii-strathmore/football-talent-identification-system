from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from users.models import OneTimeCode, User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WelcomeEmailTests(TestCase):
    def verify(self, role):
        user = User.objects.create_user('amani@example.com', 'Talanta#2026', full_name='Amani Otieno', role=role)
        user.is_active = False
        user.save()
        OneTimeCode.objects.create(user=user, code='123456', method='email', purpose='verify',
                                   expires_at=timezone.now() + timedelta(minutes=15))
        session = self.client.session
        session['pending_user_id'] = user.id
        session.save()
        response = self.client.post(reverse('verify_otp'), {'code': '123456'})
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        return mail.outbox[-1]

    def test_player_gets_branded_welcome(self):
        email = self.verify('player')
        self.assertIn('verified', email.subject)
        html = email.alternatives[0][0]
        self.assertIn('Karibu sana, Amani!', html)
        self.assertIn('banner-welcome.jpg', html)
        self.assertIn('Start my journey', html)
        self.assertIn('Upload your best football videos', email.body)

    def test_scout_welcome_mentions_review(self):
        email = self.verify('scout')
        self.assertIn('reviewing your verification document', email.alternatives[0][0])
