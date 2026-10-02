import json
import re
import tempfile
from datetime import date
from types import SimpleNamespace
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from players.models import PlayerProfile
from scouts.models import Scout
from users.models import OneTimeCode, User


def latest_code(to):
    body = [m for m in mail.outbox if to in m.to][-1].body
    return re.search(r'\b(\d{6})\b', body).group(1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MEDIA_ROOT=tempfile.mkdtemp())
class LoginAndCodeLimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('amani@gmail.com', 'Talanta#2026', full_name='Amani Otieno')

    def test_login_locks_after_five_wrong_passwords(self):
        for _ in range(5):
            self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'Talanta#2026'}, follow=True)
        self.assertContains(response, 'Too many wrong attempts')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_correct_password_clears_earlier_mistakes(self):
        for _ in range(4):
            self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'wrong'})
        self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'Talanta#2026'})
        self.client.logout()
        for _ in range(4):
            self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'email': 'amani@gmail.com', 'password': 'Talanta#2026'})
        self.assertEqual(response.status_code, 302)

    def test_verification_code_guessing_is_stopped(self):
        self.user.is_active = False
        self.user.save()
        session = self.client.session
        session['pending_user_id'] = self.user.id
        session.save()
        self.client.post(reverse('resend_otp'))
        real = latest_code('amani@gmail.com')
        for _ in range(5):
            self.client.post(reverse('verify_otp'), {'code': '000000' if real != '000000' else '111111'})
        self.client.post(reverse('verify_otp'), {'code': real})
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)  # the real code no longer works after too many guesses

    def test_codes_cannot_be_sent_again_straight_away(self):
        self.user.is_active = False
        self.user.save()
        session = self.client.session
        session['pending_user_id'] = self.user.id
        session.save()
        self.client.post(reverse('resend_otp'))
        self.client.post(reverse('resend_otp'))
        self.assertEqual(OneTimeCode.objects.filter(user=self.user, purpose='verify').count(), 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MEDIA_ROOT=tempfile.mkdtemp(), EMAIL_DNS_CHECK=False)
class EmailChangeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('amani@gmail.com', 'Talanta#2026', full_name='Amani Otieno')
        self.profile = PlayerProfile.objects.create(user=self.user, full_name='Amani Otieno', date_of_birth=date(2004, 5, 10),
                                                    age=22, position='Forward', location='Nairobi')
        self.client.force_login(self.user)
        self.url = reverse('account_email')

    def post(self, **data):
        return self.client.post(self.url, {'next': '/player/profile/', **data})

    def test_login_email_changes_only_after_the_code(self):
        self.post(action='change', new_email='amani.new@gmail.com')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'amani@gmail.com')
        self.assertEqual(self.user.pending_email, 'amani.new@gmail.com')
        self.post(action='verify', code='000000' if latest_code('amani.new@gmail.com') != '000000' else '111111')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'amani@gmail.com')
        self.post(action='verify', code=latest_code('amani.new@gmail.com'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'amani.new@gmail.com')
        self.assertEqual(self.user.pending_email, '')
        # The old address is told about the change.
        self.assertIn('Login Email Was Changed', [m for m in mail.outbox if 'amani@gmail.com' in m.to][-1].subject)
        self.client.logout()
        self.assertEqual(self.client.post(reverse('login'), {'email': 'amani.new@gmail.com', 'password': 'Talanta#2026'}).status_code, 302)

    def test_taken_email_cannot_be_used(self):
        User.objects.create_user('taken@gmail.com', 'Talanta#2026', full_name='Taken')
        response = self.client.post(self.url, {'next': '/player/profile/', 'action': 'change', 'new_email': 'Taken@gmail.com'}, follow=True)
        self.assertContains(response, 'already has a Talanta Soka account')
        self.user.refresh_from_db()
        self.assertEqual(self.user.pending_email, '')

    def test_contact_email_needs_verifying_before_scouts_see_it(self):
        scout_user = User.objects.create_user('coach@gmail.com', 'Talanta#2026', full_name='Coach', role='scout')
        Scout.objects.create(user=scout_user, organization='Gor Mahia Youth', specialization='general', verified=True,
                             verification_status='approved',
                             verification_document=SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf'))
        self.profile.contact_email = 'amani.contact@gmail.com'
        self.profile.consent_to_share_contact = True
        self.profile.save()
        from users.email_change import contact_email_changed
        contact_email_changed(self.profile, '')
        scout = self.client_class()
        scout.force_login(scout_user)
        self.assertNotContains(scout.get(reverse('scout_player_directory')), 'amani.contact@gmail.com')
        self.assertContains(self.client.get(reverse('player_profile')), 'Pending verification')
        self.post(action='contact_send')
        self.post(action='contact_verify', code=latest_code('amani.contact@gmail.com'))
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.contact_email_verified_at)
        self.assertContains(scout.get(reverse('scout_player_directory')), 'amani.contact@gmail.com')

    def test_contact_email_same_as_login_email_is_verified_at_once(self):
        from users.email_change import contact_email_changed
        self.profile.contact_email = 'Amani@gmail.com'
        self.profile.save()
        contact_email_changed(self.profile, '')
        self.profile.refresh_from_db()
        self.assertIsNotNone(self.profile.contact_email_verified_at)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BackupTests(TestCase):
    def test_only_the_main_administrator_can_download_a_backup(self):
        staff = User.objects.create_user('staff@example.com', 'Talanta#2026', full_name='Staff')
        staff.is_staff = True
        staff.save()
        self.client.force_login(staff)
        self.assertEqual(self.client.get(reverse('admin_backup')).status_code, 302)
        boss = User.objects.create_superuser('boss@example.com', 'Talanta#2026')
        self.client.force_login(boss)
        response = self.client.get(reverse('admin_backup'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(any(row['model'] == 'users.user' for row in json.loads(response.content)))


class AiAssistTests(TestCase):
    def setUp(self):
        self.player = User.objects.create_user('amani@gmail.com', 'Talanta#2026', full_name='Amani')
        self.scout = User.objects.create_user('coach@gmail.com', 'Talanta#2026', full_name='Coach', role='scout')

    @override_settings(ANTHROPIC_API_KEY='')
    def test_switched_off_without_a_key(self):
        self.client.force_login(self.player)
        res = self.client.post(reverse('ai_assist'), {'kind': 'bio', 'notes': 'fast winger'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('not switched on yet', res.json()['message'])

    def test_unverified_scouts_and_wrong_kinds_are_refused(self):
        self.client.force_login(self.scout)
        self.assertEqual(self.client.post(reverse('ai_assist'), {'kind': 'opportunity', 'notes': 'trials'}).status_code, 403)
        self.client.force_login(self.player)
        self.assertEqual(self.client.post(reverse('ai_assist'), {'kind': 'opportunity', 'notes': 'trials'}).status_code, 403)

    @override_settings(ANTHROPIC_API_KEY='test-key')
    def test_player_bio_draft(self):
        fake = SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=json.dumps({'text': 'I am a fast left winger.'}))])
        self.client.force_login(self.player)
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.beta.messages.create.return_value = fake
            res = self.client.post(reverse('ai_assist'), {'kind': 'bio', 'notes': 'fast left winger'}).json()
        self.assertEqual(res, {'ok': True, 'text': 'I am a fast left winger.'})
