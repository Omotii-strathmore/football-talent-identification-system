from django.test import TestCase
from django.urls import reverse

from users.models import SiteFeedback, User


class SiteFeedbackTests(TestCase):
    def setUp(self):
        self.player = User.objects.create_user(email='p@example.com', password='x', full_name='Pat Player', role='player')
        self.client.force_login(self.player)

    def test_popup_shown_until_user_answers(self):
        page = self.client.get(reverse('player_dashboard'))
        self.assertContains(page, 'How is Talanta Soka so far?')
        self.assertNotContains(page, 'Finding talented players')  # scout-only option hidden from players

        self.client.post(reverse('submit_feedback'), {'rating': 'good'})
        page = self.client.get(reverse('player_dashboard'))
        self.assertNotContains(page, 'How is Talanta Soka so far?')

    def test_rating_then_optional_details_update_same_answer(self):
        first = self.client.post(reverse('submit_feedback'), {'rating': 'bad'}).json()
        self.client.post(reverse('submit_feedback'), {
            'rating': 'bad',
            'feedback_id': first['feedback_id'],
            'reasons': ['slow', 'phone', 'not-a-real-option'],
            'comment': 'Videos take long',
        })
        feedback = SiteFeedback.objects.get()
        self.assertEqual(feedback.reasons, ['slow', 'phone'])
        self.assertEqual(feedback.comment, 'Videos take long')
        self.assertEqual(feedback.role, 'player')

    def test_invalid_rating_rejected(self):
        response = self.client.post(reverse('submit_feedback'), {'rating': 'terrible'})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SiteFeedback.objects.exists())

    def test_admin_sees_feedback_page(self):
        SiteFeedback.objects.create(user=self.player, role='player', rating='good', reasons=['easy'], comment='Nice')
        admin = User.objects.create_superuser(email='admin@example.com', password='secret123')
        self.client.force_login(admin)
        page = self.client.get(reverse('admin_feedback'))
        self.assertContains(page, 'Easy to use')
        self.assertContains(page, 'Nice')
        self.assertNotContains(page, 'How is Talanta Soka so far?')  # admins are never asked

    def test_legal_pages_open_gmail_compose(self):
        page = self.client.get(reverse('privacy'))
        self.assertContains(page, 'https://mail.google.com/mail/?view=cm&amp;fs=1&amp;to=anelmcall%40gmail.com')
