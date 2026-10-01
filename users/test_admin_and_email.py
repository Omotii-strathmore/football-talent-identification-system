import json
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse

from users.email_check import check_email
from users.models import User


class EmailCheckTests(TestCase):
    def setUp(self):
        User.objects.create_user('taken@gmail.com', 'Talanta#2026', full_name='Taken')

    def test_rules(self):
        self.assertIsNone(check_email('New.Player@Gmail.com', check_dns=False)[1])
        self.assertEqual(check_email('new.player@Gmail.com', check_dns=False)[0], 'new.player@gmail.com')
        self.assertIn('already has', check_email('TAKEN@gmail.com', check_dns=False)[1])
        email, problem, suggestion = check_email('amani@gmial.com', check_dns=False)
        self.assertEqual(suggestion, 'amani@gmail.com')
        self.assertIn('Temporary', check_email('x@mailinator.com', check_dns=False)[1])
        self.assertIn('does not look like', check_email('amani.gmail.com', check_dns=False)[1])

    def test_unreachable_domain_is_rejected(self):
        with mock.patch('users.email_check.domain_accepts_email', return_value=False):
            self.assertIn('cannot receive emails', check_email('a@nosuchdomain-talanta.ke', check_dns=True)[1])

    def test_live_check_endpoint(self):
        res = self.client.get(reverse('check_email'), {'email': 'taken@gmail.com'}).json()
        self.assertFalse(res['ok'])
        self.assertIn('already has', res['message'])
        self.assertTrue(self.client.get(reverse('check_email'), {'email': 'fresh@gmail.com'}).json()['ok'])

    def test_registration_refuses_taken_email_in_any_capitals(self):
        response = self.client.post(reverse('register'), {
            'full_name': 'Copy Cat', 'email': 'Taken@Gmail.com', 'role': 'player',
            'password': 'Talanta#2026', 'confirm_password': 'Talanta#2026', 'accept_terms': 'on',
        })
        self.assertContains(response, 'already has a Talanta Soka account')
        self.assertEqual(User.objects.filter(email__iexact='taken@gmail.com').count(), 1)

    def test_login_ignores_capitals(self):
        response = self.client.post(reverse('login'), {'email': 'TAKEN@GMAIL.COM', 'password': 'Talanta#2026'})
        self.assertEqual(response.status_code, 302)


class AdminUserToggleTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin@example.com', 'Talanta#2026', full_name='Admin')
        self.admin.is_staff = True
        self.admin.save()
        self.player = User.objects.create_user('amani@example.com', 'Talanta#2026', full_name='Amani Otieno')
        self.client.force_login(self.admin)

    def test_admin_can_only_switch_active_and_staff(self):
        self.client.post(reverse('admin_update_user', args=[self.player.id]), {
            'is_staff': 'on', 'full_name': 'Hacked Name', 'email': 'hacked@example.com', 'password': 'x',
        })
        self.player.refresh_from_db()
        self.assertTrue(self.player.is_staff)
        self.assertFalse(self.player.is_active)  # box left unticked switches the account off
        self.assertEqual(self.player.full_name, 'Amani Otieno')
        self.assertEqual(self.player.email, 'amani@example.com')
        self.assertTrue(self.player.check_password('Talanta#2026'))

    def test_admin_cannot_lock_themselves_out(self):
        self.client.post(reverse('admin_update_user', args=[self.admin.id]), {})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(self.admin.is_staff)

    def test_users_page_has_no_password_box(self):
        response = self.client.get(reverse('admin_users'))
        self.assertContains(response, 'Amani Otieno')
        self.assertNotContains(response, 'type="password"')


class AiDraftTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin@example.com', 'Talanta#2026', full_name='Admin')
        self.admin.is_staff = True
        self.admin.save()
        self.client.force_login(self.admin)

    @override_settings(ANTHROPIC_API_KEY='')
    def test_without_key_the_button_explains_it_is_off(self):
        res = self.client.post(reverse('admin_update_ai_draft'), {'notes': 'eye button'})
        self.assertEqual(res.status_code, 400)
        self.assertIn('not switched on yet', res.json()['message'])

    @override_settings(ANTHROPIC_API_KEY='test-key')
    def test_with_key_the_draft_fills_the_form(self):
        draft = {'title': 'Safer, smoother sign-up', 'teaser': 'Karibu! Here is what is new.', 'points': ['An eye button shows your password']}
        fake = SimpleNamespace(stop_reason='end_turn', content=[SimpleNamespace(type='text', text=json.dumps(draft))])
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.beta.messages.create.return_value = fake
            res = self.client.post(reverse('admin_update_ai_draft'), {'notes': 'eye button for passwords'}).json()
        self.assertTrue(res['ok'])
        self.assertEqual(res['title'], 'Safer, smoother sign-up')
        self.assertEqual(res['points'], ['An eye button shows your password'])

    def test_players_cannot_use_it(self):
        player = User.objects.create_user('p@example.com', 'Talanta#2026', full_name='Player')
        self.client.force_login(player)
        self.assertEqual(self.client.post(reverse('admin_update_ai_draft'), {'notes': 'x'}).status_code, 302)
