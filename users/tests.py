from django.test import TestCase
from django.urls import reverse

from .models import User


class AdminReportsPdfExportTests(TestCase):
    def test_admin_can_export_summary_report_as_pdf(self):
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='StrongPass123',
            full_name='Admin User',
        )

        self.client.force_login(admin_user)
        response = self.client.get(
            reverse('admin_reports'),
            {'report': 'summary', 'action': 'generate', 'format': 'pdf'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
