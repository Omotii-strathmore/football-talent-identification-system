from django.test import TestCase, override_settings
from django.urls import reverse

from players.models import PlayerProfile
from users.models import User

PASSWORD = 'Str0ngPass!x'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class UnfinishedSignupTests(TestCase):
    """Someone who stops after step 1 never gets a code (it is sent after step 2), so they must be able to carry on."""

    def _register(self, email, name='Fiona Akinyi'):
        return self.client.post(reverse('register'), {
            'full_name': name, 'email': email, 'role': 'player',
            'password': PASSWORD, 'confirm_password': PASSWORD, 'accept_terms': 'on',
        })

    def test_logging_in_after_step_one_goes_back_to_step_two(self):
        self._register('fiona@example.com')
        self.client.session.flush()
        response = self.client.post(reverse('login'), {'email': 'fiona@example.com', 'password': PASSWORD}, follow=True)
        self.assertRedirects(response, reverse('complete_profile'))
        self.assertContains(response, 'Finish step 2')

    def test_signing_up_again_replaces_the_unfinished_account(self):
        self._register('fiona@example.com')
        first_id = User.objects.get(email='fiona@example.com').pk
        self.client.session.flush()
        self.assertEqual(self.client.get(reverse('check_email'), {'email': 'Fiona@example.com'}).json()['ok'], True)
        response = self._register('Fiona@Example.com', name='Fiona A. Akinyi')
        self.assertRedirects(response, reverse('complete_profile'), fetch_redirect_response=False)
        user = User.objects.get(email__iexact='fiona@example.com')
        self.assertNotEqual(user.pk, first_id)
        self.assertEqual(user.full_name, 'Fiona A. Akinyi')

    def test_accounts_that_finished_step_two_are_still_taken(self):
        user = User.objects.create_user('kevin@example.com', PASSWORD, full_name='Kevin Mwangi', role='player')
        user.is_active = False
        user.save()
        PlayerProfile.objects.create(user=user, full_name='Kevin Mwangi', age=22, position='Defender', location='Kiambu')
        self.assertEqual(self.client.get(reverse('check_email'), {'email': 'kevin@example.com'}).json()['ok'], False)
        self._register('kevin@example.com')
        self.assertEqual(User.objects.filter(email__iexact='kevin@example.com').count(), 1)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WelcomeBlessingTests(TestCase):
    def test_welcome_email_carries_the_verse_and_blessing(self):
        from django.core import mail
        from users.emails import send_welcome_email
        user = User.objects.create_user('neema@example.com', PASSWORD, full_name='Neema Atieno', role='scout')
        send_welcome_email(user)
        message = mail.outbox[-1]
        self.assertIn('As iron sharpens iron', message.body)
        self.assertIn('Mungu akubariki', message.alternatives[0][0])
