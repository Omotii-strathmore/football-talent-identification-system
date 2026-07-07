from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from players.models import PlayerProfile, PlayerVideo
from scouts.models import Scout, ScoutVideoFeedback
from users.models import User


class FeedbackAndAuthFlowTests(TestCase):
    def test_login_shows_success_message(self):
        user = User.objects.create_user(
            email='player@example.com',
            password='StrongPass123',
            full_name='Test Player',
            role='player',
        )
        PlayerProfile.objects.create(
            user=user,
            full_name='Test Player',
            age=20,
            position='Forward',
            location='Nairobi',
        )

        response = self.client.post(
            reverse('login'),
            {'email': user.email, 'password': 'StrongPass123'},
            follow=True,
        )

        self.assertRedirects(response, reverse('player_dashboard'))
        self.assertContains(response, 'Login successful')

    def test_player_can_edit_feedback_response(self):
        player = User.objects.create_user(
            email='player2@example.com',
            password='StrongPass123',
            full_name='Player Two',
            role='player',
        )
        profile = PlayerProfile.objects.create(
            user=player,
            full_name='Player Two',
            age=22,
            position='Midfielder',
            location='Mombasa',
        )
        video = PlayerVideo.objects.create(
            profile=profile,
            title='Highlight clip',
            video_file=SimpleUploadedFile('clip.mp4', b'data', content_type='video/mp4'),
        )
        scout = User.objects.create_user(
            email='scout@example.com',
            password='StrongPass123',
            full_name='Scout One',
            role='scout',
        )
        Scout.objects.create(
            user=scout,
            organization='Elite Academy',
            specialization='general',
            verification_document=SimpleUploadedFile('doc.pdf', b'data', content_type='application/pdf'),
        )
        feedback = ScoutVideoFeedback.objects.create(
            scout=scout,
            video=video,
            comment='Keep improving.',
        )

        self.client.force_login(player)
        response = self.client.post(
            reverse('player_dashboard'),
            {'feedback_id': feedback.id, 'player_reply': 'Thanks for the note.', 'player_reaction': '👍🏾'},
            follow=True,
        )

        self.assertContains(response, 'Your reply has been sent to the scout.')
        feedback.refresh_from_db()
        self.assertEqual(feedback.player_reply, 'Thanks for the note.')
        self.assertEqual(feedback.player_reaction, '👍🏾')
        self.assertTrue(feedback.is_seen)
