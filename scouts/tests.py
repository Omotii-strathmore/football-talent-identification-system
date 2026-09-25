from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse

from players.models import PlayerProfile
from scouts.models import Scout, ScoutPlayerShortlist
from users.models import User


class ScoutShortlistTests(TestCase):
    def setUp(self):
        self.scout_user = User.objects.create_user(
            email='scout@example.com',
            password='secret123',
            full_name='Scout One',
            role='scout',
        )
        self.scout_profile = Scout.objects.create(
            user=self.scout_user,
            organization='Talent FC',
            specialization='General',
            verification_document=ContentFile(b'pdf-bytes', name='verification.pdf'),
            verified=True,
            verification_status='approved',
        )
        self.player_user = User.objects.create_user(
            email='player@example.com',
            password='secret123',
            full_name='Player One',
            role='player',
        )
        self.player_profile = PlayerProfile.objects.create(
            user=self.player_user,
            full_name='Player One',
            age=20,
            position='Forward',
            location='Nairobi',
        )

    def test_scout_can_save_and_unsave_player_profiles(self):
        self.client.force_login(self.scout_user)

        response = self.client.post(
            reverse('scout_toggle_shortlist'),
            {'profile_id': self.player_profile.id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ScoutPlayerShortlist.objects.filter(scout=self.scout_user, profile=self.player_profile).exists()
        )

        response = self.client.post(
            reverse('scout_toggle_shortlist'),
            {'profile_id': self.player_profile.id},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            ScoutPlayerShortlist.objects.filter(scout=self.scout_user, profile=self.player_profile).exists()
        )

    def test_shortlist_page_lists_saved_profiles(self):
        ScoutPlayerShortlist.objects.create(scout=self.scout_user, profile=self.player_profile)
        self.client.force_login(self.scout_user)

        response = self.client.get(reverse('scout_shortlist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.player_profile.full_name)

    def test_unverified_scout_cannot_view_players(self):
        self.scout_profile.verified = False
        self.scout_profile.verification_status = 'pending'
        self.scout_profile.save()
        self.client.force_login(self.scout_user)

        for url_name in ['scout_player_directory', 'scout_shortlist', 'scout_player_recommendations']:
            response = self.client.get(reverse(url_name))
            self.assertRedirects(response, reverse('scout_dashboard'), fetch_redirect_response=False)

        self.client.post(reverse('scout_toggle_shortlist'), {'profile_id': self.player_profile.id})
        self.assertFalse(ScoutPlayerShortlist.objects.filter(scout=self.scout_user).exists())
