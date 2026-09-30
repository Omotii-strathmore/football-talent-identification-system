import re
from datetime import date, timedelta

from django.core import mail
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse

from opportunities.models import Application, Opportunity
from players.guardian import make_token
from players.models import PlayerProfile
from scouts.models import Scout
from users.models import User


def _born(years_ago):
    today = date.today()
    return date(today.year - years_ago, 1, 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class GuardianApprovalTests(TestCase):
    def setUp(self):
        self.scout_user = User.objects.create_user(email='scout@example.com', password='x', full_name='Scout', role='scout')
        Scout.objects.create(
            user=self.scout_user, organization='Talent FC', specialization='general',
            verification_document=ContentFile(b'pdf', name='v.pdf'), verified=True, verification_status='approved',
        )

    def _register_minor(self, guardian_email='mum@example.com'):
        self.client.post(reverse('register'), {
            'full_name': 'Kid Player', 'email': 'kid@example.com', 'role': 'player',
            'password': 'Str0ngPass!x', 'confirm_password': 'Str0ngPass!x', 'accept_terms': 'on',
        })
        return self.client.post(reverse('complete_profile'), {
            'date_of_birth': _born(15).isoformat(), 'position': 'Forward', 'location': 'Nairobi',
            'guardian_consent': 'on', 'guardian_name': 'Mary Mum', 'guardian_email': guardian_email,
        })

    def _scout_sees_kid(self):
        client = self.client_class()
        client.force_login(self.scout_user)
        return 'Kid Player' in client.get(reverse('scout_player_directory') + '?position=').content.decode()

    def test_minor_must_give_guardian_details(self):
        self.client.post(reverse('register'), {
            'full_name': 'Kid Player', 'email': 'kid@example.com', 'role': 'player',
            'password': 'Str0ngPass!x', 'confirm_password': 'Str0ngPass!x', 'accept_terms': 'on',
        })
        response = self.client.post(reverse('complete_profile'), {
            'date_of_birth': _born(15).isoformat(), 'position': 'Forward', 'location': 'Nairobi', 'guardian_consent': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlayerProfile.objects.exists())

    def test_guardian_email_cannot_be_the_players_own(self):
        response = self._register_minor(guardian_email='kid@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlayerProfile.objects.exists())

    def test_guardian_is_emailed_and_minor_hidden_until_approved(self):
        self._register_minor()
        profile = PlayerProfile.objects.get()
        guardian_mail = [m for m in mail.outbox if 'mum@example.com' in m.to]
        self.assertEqual(len(guardian_mail), 1)
        self.assertIn('Mary Mum', guardian_mail[0].body)
        link = re.search(r'http\S+/player/guardian/\S+/', guardian_mail[0].body).group(0)
        self.assertFalse(self._scout_sees_kid())

        page = self.client_class().get(link)
        self.assertContains(page, 'I approve')
        self.client_class().post(link, {'decision': 'approve'})
        profile.refresh_from_db()
        self.assertIsNotNone(profile.guardian_approved_at)
        self.assertTrue(self._scout_sees_kid())

        self.client_class().post(link, {'decision': 'decline'})
        profile.refresh_from_db()
        self.assertIsNone(profile.guardian_approved_at)
        self.assertFalse(self._scout_sees_kid())

    def test_minor_cannot_apply_until_approved(self):
        self._register_minor()
        kid = User.objects.get(email='kid@example.com')
        kid.is_active = True
        kid.save()
        opportunity = Opportunity.objects.create(
            scout=self.scout_user, title='Trial', organization='Talent FC', description='d',
            location='Nairobi', deadline=date.today() + timedelta(days=5),
        )
        self.client.force_login(kid)
        self.client.post(reverse('apply_opportunity', args=[opportunity.id]), {'motivation': 'Pick me'})
        self.assertFalse(Application.objects.exists())

        profile = PlayerProfile.objects.get()
        self.client_class().post(reverse('guardian_review', args=[make_token(profile)]), {'decision': 'approve'})
        self.client.post(reverse('apply_opportunity', args=[opportunity.id]), {'motivation': 'Pick me'})
        self.assertTrue(Application.objects.exists())

    def test_old_link_stops_working_after_email_change_and_bad_links_404(self):
        self._register_minor()
        profile = PlayerProfile.objects.get()
        old_token = make_token(profile)
        kid = User.objects.get(email='kid@example.com')
        kid.is_active = True
        kid.save()
        self.client.force_login(kid)
        self.assertContains(self.client.get(reverse('player_dashboard')), 'Waiting for your parent or guardian')
        self.client.post(reverse('guardian_resend'), {'guardian_email': 'dad@example.com'})
        profile.refresh_from_db()
        self.assertEqual(profile.guardian_email, 'dad@example.com')
        self.assertEqual(self.client_class().get(reverse('guardian_review', args=[old_token])).status_code, 404)
        self.assertEqual(self.client_class().get(reverse('guardian_review', args=['not-a-real-token'])).status_code, 404)
        self.assertTrue(any('dad@example.com' in m.to for m in mail.outbox))

    def test_adults_are_visible_without_guardian(self):
        adult = User.objects.create_user(email='adult@example.com', password='x', full_name='Adult Player', role='player')
        PlayerProfile.objects.create(user=adult, full_name='Adult Player', date_of_birth=_born(22), age=22,
                                     position='Forward', location='Nairobi')
        client = self.client_class()
        client.force_login(self.scout_user)
        self.assertContains(client.get(reverse('scout_player_directory') + '?position='), 'Adult Player')
