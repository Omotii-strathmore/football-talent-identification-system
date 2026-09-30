import tempfile

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from scouts.models import Scout
from users.models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MEDIA_ROOT=tempfile.mkdtemp())
class ScoutDecisionEmailTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin@example.com', 'Talanta#2026', full_name='Admin', role='player')
        self.admin.is_staff = True
        self.admin.save()
        self.user = User.objects.create_user('coach@example.com', 'Talanta#2026', full_name='Otieno Coach', role='scout')
        self.scout = Scout.objects.create(
            user=self.user, organization='Gor Mahia Youth Academy', specialization='attacking',
            verification_document=SimpleUploadedFile('doc.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
        )

    def test_approval_emails_the_scout(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_approve_scout', args=[self.scout.id]))
        email = mail.outbox[-1]
        self.assertEqual(email.to, ['coach@example.com'])
        self.assertIn("verified, Coach", email.subject)
        html = email.alternatives[0][0]
        self.assertIn('Karibu, Coach Otieno!', html)
        self.assertIn('banner-coach.jpg', html)
        self.assertIn('Start scouting', html)

    def test_rejection_emails_reason_and_try_again_link(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_reject_scout', args=[self.scout.id]), {'reason': 'The letter was not signed.'})
        email = mail.outbox[-1]
        self.assertIn('could not verify', email.subject)
        html = email.alternatives[0][0]
        self.assertIn('The letter was not signed.', html)
        self.assertIn('/login/?next=/scout/verification/resubmit/', html)
        self.assertIn('Try again', html)

    def test_try_again_sends_document_back_for_review(self):
        self.scout.verification_status = 'rejected'
        self.scout.save()
        # The email link: log in, then land on the try-again page.
        response = self.client.post(
            reverse('login') + '?next=/scout/verification/resubmit/',
            {'email': 'coach@example.com', 'password': 'Talanta#2026', 'next': '/scout/verification/resubmit/'},
        )
        self.assertRedirects(response, reverse('scout_resubmit_verification'), fetch_redirect_response=False)
        response = self.client.post(reverse('scout_resubmit_verification'), {
            'organization': 'Gor Mahia Youth Academy',
            'verification_document': SimpleUploadedFile('licence.pdf', b'%PDF-1.4 new', content_type='application/pdf'),
        })
        self.assertRedirects(response, reverse('scout_dashboard'), fetch_redirect_response=False)
        self.scout.refresh_from_db()
        self.assertEqual(self.scout.verification_status, 'pending')
        self.assertFalse(self.scout.verified)

    def test_login_ignores_links_to_other_sites(self):
        response = self.client.post(reverse('login'), {
            'email': 'coach@example.com', 'password': 'Talanta#2026', 'next': 'https://evil.example.com/',
        })
        self.assertRedirects(response, reverse('scout_dashboard'), fetch_redirect_response=False)
