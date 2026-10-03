import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from opportunities.models import Opportunity
from players.test_categories import make_player
from scouts.models import Scout
from users.models import AdminNotification, User
from users.notify import check_milestone


def pdf(name='doc.pdf'):
    return SimpleUploadedFile(name, b'%PDF-1.4 test', content_type='application/pdf')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ScoutReverifyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('coach@gmail.com', 'Talanta#2026', full_name='Coach Grace', role='scout')
        self.scout = Scout.objects.create(user=self.user, organization='Thika Queens Academy', specialization='general',
                                          verified=True, verification_status='approved', scouts_for='starlets',
                                          verification_document=pdf())
        self.client.force_login(self.user)

    def post(self, **data):
        base = {'organization': self.scout.organization, 'specialization': self.scout.specialization}
        base.update(data)
        return self.client.post(reverse('scout_edit_details'), base)

    def test_changing_organisation_needs_a_document_and_new_approval(self):
        page = self.post(organization='Kibera Girls Soccer Academy')
        self.assertContains(page, 'Please upload a document that shows the new details')
        self.scout.refresh_from_db()
        self.assertEqual(self.scout.verification_status, 'approved')
        self.post(organization='Kibera Girls Soccer Academy', verification_document=pdf('new.pdf'))
        self.scout.refresh_from_db()
        self.assertEqual((self.scout.organization, self.scout.verification_status, self.scout.verified),
                         ('Kibera Girls Soccer Academy', 'pending', False))
        note = AdminNotification.objects.get()
        self.assertEqual(note.kind, 'scout_changed')
        self.assertIn('Coach Grace', note.message)

    def test_same_details_or_only_capital_letters_keep_the_scout_verified(self):
        self.post(organization='thika queens academy')
        self.scout.refresh_from_db()
        self.assertEqual(self.scout.verification_status, 'approved')
        self.assertFalse(AdminNotification.objects.exists())

    def test_resending_a_document_notifies_the_admin(self):
        Scout.objects.filter(pk=self.scout.pk).update(verification_status='rejected', verified=False)
        self.client.post(reverse('scout_resubmit_verification'), {'organization': 'Thika Queens Academy', 'scouts_for': 'starlets',
                                                                  'verification_document': pdf('again.pdf')})
        self.assertTrue(AdminNotification.objects.filter(kind='scout_resubmit').exists())

    def test_post_page_with_trial_date(self):
        deadline = timezone.localdate() + timedelta(days=5)
        self.client.post(reverse('post_opportunity'), {
            'title': 'U-19 Trials', 'organization': 'Thika Queens Academy', 'category': 'starlets',
            'description': 'Bring boots.', 'location': 'Thika', 'deadline': deadline.isoformat(),
            'event_date': (deadline + timedelta(days=2)).isoformat()})
        trial = Opportunity.objects.get(title='U-19 Trials')
        self.assertEqual(trial.event_date, deadline + timedelta(days=2))
        page = self.client.get(reverse('post_opportunity'))
        self.assertContains(page, 'Who is it for?')
        self.assertContains(page, 'U-19 Trials')


class AdminNotificationTests(TestCase):
    def test_feedback_milestones_and_reading(self):
        admin = User.objects.create_user('admin@gmail.com', 'Talanta#2026', full_name='Admin')
        admin.is_staff = True
        admin.save()
        player = make_player('jack@gmail.com', 'Jack Sese', 'stars')
        self.client.force_login(player)
        self.client.post(reverse('submit_feedback'), {'rating': 'good'})
        self.assertTrue(AdminNotification.objects.filter(kind='feedback').exists())
        for number in range(3):
            make_player(f'p{number}@gmail.com', f'Player {number}', 'stars')
        check_milestone('player')  # 4 players: nothing yet
        self.assertFalse(AdminNotification.objects.filter(kind='milestone').exists())
        make_player('p9@gmail.com', 'Player 9', 'stars')
        check_milestone('player')  # 5 players
        self.assertTrue(AdminNotification.objects.filter(kind='milestone', message__startswith='5 players').exists())

        self.client.force_login(admin)
        dashboard = self.client.get(reverse('admin_dashboard'))
        self.assertContains(dashboard, '2 new')
        note = AdminNotification.objects.get(kind='feedback')
        self.assertRedirects(self.client.get(reverse('admin_notification_open', args=[note.id])), reverse('admin_feedback'),
                             fetch_redirect_response=False)
        note.refresh_from_db()
        self.assertIsNotNone(note.read_at)
        self.client.post(reverse('admin_notifications_read_all'))
        self.assertFalse(AdminNotification.objects.filter(read_at__isnull=True).exists())
