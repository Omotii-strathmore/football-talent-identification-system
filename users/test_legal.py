from datetime import date

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.urls import reverse

from players.models import PlayerProfile, PlayerVideo
from users.models import User


def _years_ago(years):
    today = date.today()
    return date(today.year - years, 1, 1).isoformat()


class LegalPagesAndConsentTests(TestCase):
    def test_privacy_and_terms_pages_render(self):
        self.assertContains(self.client.get(reverse('privacy')), 'Privacy Policy')
        self.assertContains(self.client.get(reverse('terms')), 'Terms of Use')

    def _register(self, email, accept_terms=True):
        data = {
            'full_name': 'Test Person',
            'email': email,
            'role': 'player',
            'password': 'Str0ngPass!x',
            'confirm_password': 'Str0ngPass!x',
        }
        if accept_terms:
            data['accept_terms'] = 'on'
        return self.client.post(reverse('register'), data)

    def test_registration_requires_accepting_terms(self):
        response = self._register('noterms@example.com', accept_terms=False)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='noterms@example.com').exists())

    def test_registration_records_terms_acceptance(self):
        self._register('terms@example.com')
        user = User.objects.get(email='terms@example.com')
        self.assertIsNotNone(user.terms_accepted_at)

    def test_minor_needs_guardian_consent(self):
        self._register('minor@example.com')
        response = self.client.post(reverse('complete_profile'), {
            'date_of_birth': _years_ago(15),
            'position': 'Forward',
            'location': 'Nairobi',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PlayerProfile.objects.filter(user__email='minor@example.com').exists())

        self.client.post(reverse('complete_profile'), {
            'date_of_birth': _years_ago(15),
            'position': 'Forward',
            'location': 'Nairobi',
            'guardian_consent': 'on',
        })
        profile = PlayerProfile.objects.get(user__email='minor@example.com')
        self.assertIsNotNone(profile.guardian_consent_at)

    def test_adult_does_not_need_guardian_consent(self):
        self._register('adult@example.com')
        self.client.post(reverse('complete_profile'), {
            'date_of_birth': _years_ago(22),
            'position': 'Forward',
            'location': 'Nairobi',
        })
        profile = PlayerProfile.objects.get(user__email='adult@example.com')
        self.assertIsNone(profile.guardian_consent_at)


class AccountDeletionRemovesFilesTests(TestCase):
    def test_deleting_account_deletes_uploaded_files(self):
        admin = User.objects.create_superuser(email='admin@example.com', password='secret123')
        player = User.objects.create_user(email='p@example.com', password='x', full_name='P', role='player')
        profile = PlayerProfile.objects.create(user=player, full_name='P', age=16, position='Forward', location='Nairobi')
        video = PlayerVideo(profile=profile, title='Clip')
        video.video_file.save('deletion_test_clip.mp4', ContentFile(b'data'))
        stored_name = video.video_file.name
        self.assertTrue(default_storage.exists(stored_name))

        self.client.force_login(admin)
        self.client.post(reverse('admin_delete_user', args=[player.id]))

        self.assertFalse(User.objects.filter(id=player.id).exists())
        self.assertFalse(default_storage.exists(stored_name))
