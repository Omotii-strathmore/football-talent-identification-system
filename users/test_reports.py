from django.test import TestCase
from django.urls import reverse
from users.models import User
from players.models import PlayerProfile


class AdminReportsTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='secret123',
            full_name='Admin User',
            role='scout',
        )
        self.admin.is_staff = True
        self.admin.save()

    def test_admin_reports_page_renders_with_filters(self):
        PlayerProfile.objects.create(
            user=self.admin,
            full_name='Test Player',
            age=20,
            position='Midfielder',
            location='Nairobi',
        )
        self.client.login(email='admin@example.com', password='secret123')
        response = self.client.get(reverse('admin_reports'), {
            'report': 'summary',
            'format': 'csv',
            'start_date': '2024-01-01',
            'end_date': '2026-12-31',
            'position': 'Midfielder',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Generate Reports')
