import re
import tempfile
from datetime import date, timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from players.models import PlayerJourneyCheckIn, PlayerJourneyGoal, PlayerProfile, PlayerVideo
from scouts.models import Scout, ScoutPlayerContactRequest
from users.models import User


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class PlayerJourneyTests(TestCase):
    def setUp(self):
        self.player = User.objects.create_user(
            'player@example.com',
            'StrongPass123',
            full_name='Amani Player',
            role='player',
        )
        self.profile = PlayerProfile.objects.create(
            user=self.player,
            full_name='Amani Player',
            date_of_birth=date(2004, 1, 1),
            age=22,
            position='Forward',
            location='Nairobi',
        )

    def test_player_can_add_goals_and_quarterly_checkins(self):
        self.client.force_login(self.player)
        response = self.client.post(reverse('player_journey_update'), {
            'action': 'add_goal',
            'title': 'Improve my weaker-foot passing',
            'target_date': '2026-09-01',
        })
        self.assertRedirects(response, reverse('player_dashboard'), fetch_redirect_response=False)
        goal = PlayerJourneyGoal.objects.get(profile=self.profile)
        self.assertEqual(goal.title, 'Improve my weaker-foot passing')
        self.assertFalse(goal.is_complete)

        self.client.post(reverse('player_journey_update'), {
            'action': 'check_in',
            'update': 'I have trained with the academy every week.',
            'next_step': 'Build stamina before the next trial.',
        })
        checkin = PlayerJourneyCheckIn.objects.get(profile=self.profile)
        self.assertEqual(checkin.next_step, 'Build stamina before the next trial.')

        response = self.client.post(reverse('player_journey_update'), {
            'action': 'complete_goal',
            'goal_id': goal.id,
        })
        goal.refresh_from_db()
        self.assertTrue(goal.is_complete)

    def test_quarterly_checkin_prompt_is_due_after_ninety_days(self):
        PlayerProfile.objects.filter(pk=self.profile.pk).update(
            created_at=timezone.now() - timedelta(days=91)
        )
        self.client.force_login(self.player)
        response = self.client.get(reverse('player_dashboard'))
        self.assertContains(response, 'Your quarterly check-in is due.')

    def test_player_can_choose_public_or_private_progress(self):
        self.client.force_login(self.player)
        url = reverse('player_journey_update')
        self.client.post(url, {'action': 'set_visibility', 'visibility': 'public'})
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.share_journey_with_community)
        self.client.post(url, {'action': 'set_visibility', 'visibility': 'private'})
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.share_journey_with_community)

    def test_journey_is_private_until_the_player_shares_it(self):
        scout_user = User.objects.create_user(
            'scout@example.com',
            'StrongPass123',
            full_name='Scout One',
            role='scout',
        )
        Scout.objects.create(
            user=scout_user,
            organization='Talent Academy',
            specialization='general',
            verification_document=SimpleUploadedFile('proof.pdf', b'%PDF-1.4'),
            verified=True,
            verification_status='approved',
        )
        PlayerJourneyCheckIn.objects.create(
            profile=self.profile,
            update='Private training update that should not be public.',
        )
        scout_client = self.client_class()
        scout_client.force_login(scout_user)
        directory_url = reverse('scout_player_directory')
        self.assertNotContains(scout_client.get(directory_url), 'Private training update')

        self.profile.share_journey_with_community = True
        self.profile.save(update_fields=['share_journey_with_community'])
        self.assertContains(scout_client.get(directory_url), 'Private training update')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    MEDIA_ROOT=tempfile.mkdtemp(),
)
class ScoutContactRequestTests(TestCase):
    def setUp(self):
        self.scout_user = User.objects.create_user(
            'scout@example.com',
            'StrongPass123',
            full_name='Coach One',
            role='scout',
        )
        Scout.objects.create(
            user=self.scout_user,
            organization='Talent Academy',
            specialization='general',
            verification_document=SimpleUploadedFile('proof.pdf', b'%PDF-1.4'),
            verified=True,
            verification_status='approved',
        )
        self.player = User.objects.create_user(
            'player@example.com',
            'StrongPass123',
            full_name='Amani Player',
            role='player',
        )
        self.profile = PlayerProfile.objects.create(
            user=self.player,
            full_name='Amani Player',
            date_of_birth=date(2004, 1, 1),
            age=22,
            position='Forward',
            location='Nairobi',
            contact_email='amani.contact@example.com',
            contact_email_verified_at=timezone.now(),
            consent_to_share_contact=True,
        )
        self.scout_client = self.client_class()
        self.scout_client.force_login(self.scout_user)

    def test_contact_details_are_hidden_until_adult_player_accepts(self):
        directory_url = reverse('scout_player_directory')
        self.assertNotContains(self.scout_client.get(directory_url), self.profile.contact_email)
        self.scout_client.post(reverse('scout_request_player_contact'), {
            'profile_id': self.profile.id,
            'message': 'I would like to discuss a trial opportunity.',
            'redirect_to': directory_url,
        })
        contact_request = ScoutPlayerContactRequest.objects.get(profile=self.profile)
        self.assertEqual(contact_request.status, 'pending')
        self.assertNotContains(self.scout_client.get(directory_url), self.profile.contact_email)

        player_client = self.client_class()
        player_client.force_login(self.player)
        player_client.post(
            reverse('player_contact_request_respond', args=[contact_request.id]),
            {'decision': 'accept'},
        )
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, 'accepted')
        self.assertContains(self.scout_client.get(directory_url), self.profile.contact_email)

    def test_minor_needs_guardian_approval_before_contact_is_revealed(self):
        self.profile.date_of_birth = date(2012, 1, 1)
        self.profile.age = 14
        self.profile.guardian_email = 'guardian@example.com'
        self.profile.guardian_approved_at = timezone.now()
        self.profile.save()

        directory_url = reverse('scout_player_directory')
        self.scout_client.post(reverse('scout_request_player_contact'), {
            'profile_id': self.profile.id,
            'message': 'Please consider Amani for an academy trial.',
            'redirect_to': directory_url,
        })
        contact_request = ScoutPlayerContactRequest.objects.get(profile=self.profile)
        player_client = self.client_class()
        player_client.force_login(self.player)
        player_client.post(
            reverse('player_contact_request_respond', args=[contact_request.id]),
            {'decision': 'accept'},
        )
        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, 'guardian_pending')
        self.assertNotContains(self.scout_client.get(directory_url), self.profile.contact_email)
        self.assertEqual(mail.outbox[-1].to, ['guardian@example.com'])

        html = mail.outbox[-1].alternatives[0][0]
        guardian_url = re.search(r'href="([^"]+guardian/contact-request/[^"]+)"', html).group(1)
        guardian_response = self.client.get(guardian_url)
        self.assertEqual(guardian_response.status_code, 200)
        self.client.post(guardian_url, {'decision': 'accept'})

        contact_request.refresh_from_db()
        self.assertEqual(contact_request.status, 'accepted')
        self.assertIsNotNone(contact_request.guardian_approved_at)
        self.assertContains(self.scout_client.get(directory_url), self.profile.contact_email)


class PreferredFootFilterTests(TestCase):
    def setUp(self):
        scout_user = User.objects.create_user(
            'scout@example.com',
            'StrongPass123',
            full_name='Scout One',
            role='scout',
        )
        Scout.objects.create(
            user=scout_user,
            organization='Talent Academy',
            specialization='general',
            verification_document=SimpleUploadedFile('proof.pdf', b'%PDF-1.4'),
            verified=True,
            verification_status='approved',
        )
        self.client.force_login(scout_user)
        for email, name, foot in (
            ('right@example.com', 'Right Foot Player', 'right'),
            ('left@example.com', 'Left Foot Player', 'left'),
            ('both@example.com', 'Both Feet Player', 'both'),
        ):
            user = User.objects.create_user(email, 'StrongPass123', full_name=name, role='player')
            PlayerProfile.objects.create(
                user=user,
                full_name=name,
                date_of_birth=date(2004, 1, 1),
                age=22,
                position='Forward',
                location='Nairobi',
                preferred_foot=foot,
            )

    def test_preferred_foot_filter_returns_matching_players_only(self):
        response = self.client.get(reverse('scout_player_directory'), {'preferred_foot': 'left'})
        self.assertContains(response, 'Left Foot Player')
        self.assertNotContains(response, 'Right Foot Player')
        self.assertNotContains(response, 'Both Feet Player')

    def test_invalid_preferred_foot_is_ignored(self):
        response = self.client.get(reverse('scout_player_directory'), {'preferred_foot': 'unknown'})
        self.assertContains(response, 'Select right, left, or both for preferred foot.')
        self.assertContains(response, 'Right Foot Player')
        self.assertContains(response, 'Left Foot Player')
        self.assertContains(response, 'Both Feet Player')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class PlayerCommunityTests(TestCase):
    def setUp(self):
        self.viewer = User.objects.create_user(
            'viewer@example.com',
            'StrongPass123',
            full_name='Viewer Player',
            role='player',
        )
        self.client.force_login(self.viewer)
        self.player = User.objects.create_user(
            'shared@example.com',
            'StrongPass123',
            full_name='Shared Player',
            role='player',
        )
        self.profile = PlayerProfile.objects.create(
            user=self.player,
            full_name='Shared Player',
            date_of_birth=date(2004, 1, 1),
            age=22,
            position='Midfielder',
            location='Kisumu',
            bio='A profile visible to players who sign in.',
            contact_email='private-contact@example.com',
            contact_email_verified_at=timezone.now(),
            consent_to_share_contact=True,
        )

    def test_only_opted_in_profiles_and_videos_are_visible_in_community(self):
        video = PlayerVideo.objects.create(
            profile=self.profile,
            title='Shared match highlights',
            video_file=SimpleUploadedFile('highlights.mp4', b'video', content_type='video/mp4'),
        )
        url = reverse('player_community')
        self.assertNotContains(self.client.get(url), 'Shared Player')

        self.profile.share_profile_with_players = True
        self.profile.save(update_fields=['share_profile_with_players'])
        response = self.client.get(url)
        self.assertContains(response, 'Shared Player')
        self.assertContains(response, video.title)
        self.assertContains(response, self.profile.bio)
        self.assertNotContains(response, self.profile.contact_email)

    def test_progress_only_appears_when_the_player_marks_it_public(self):
        self.profile.share_profile_with_players = True
        self.profile.save(update_fields=['share_profile_with_players'])
        PlayerJourneyCheckIn.objects.create(
            profile=self.profile,
            update='A private check-in detail.',
        )
        url = reverse('player_community')
        self.assertNotContains(self.client.get(url), 'A private check-in detail.')

        self.profile.share_journey_with_community = True
        self.profile.save(update_fields=['share_journey_with_community'])
        self.assertContains(self.client.get(url), 'A private check-in detail.')

    def test_unapproved_minor_is_not_listed_even_if_they_opt_in(self):
        minor = User.objects.create_user(
            'minor@example.com',
            'StrongPass123',
            full_name='Minor Player',
            role='player',
        )
        PlayerProfile.objects.create(
            user=minor,
            full_name='Minor Player',
            date_of_birth=date(2012, 1, 1),
            age=14,
            position='Forward',
            location='Nairobi',
            share_profile_with_players=True,
            share_journey_with_community=True,
        )
        response = self.client.get(reverse('player_community'))
        self.assertNotContains(response, 'Minor Player')
