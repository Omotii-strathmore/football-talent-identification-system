import tempfile
from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from opportunities.forms import OpportunityForm
from opportunities.models import Application, Opportunity
from opportunities.reminders import send_trial_day_reminders
from players.test_categories import make_player
from users.models import User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', MEDIA_ROOT=tempfile.mkdtemp())
class TrialFollowUpTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.scout = User.objects.create_user('coach@gmail.com', 'Talanta#2026', full_name='Coach Grace', role='scout')
        self.player = make_player('jack@gmail.com', 'Jack Sese', 'stars')

    def trial(self, event_date=None, deadline=None, title='Elite Midfield Talent Search'):
        return Opportunity.objects.create(scout=self.scout, title=title, organization='Talantafc', description='Trials',
                                          location='Nairobi', deadline=deadline or self.today, event_date=event_date, category='open')

    def apply(self, trial, status='shortlisted'):
        return Application.objects.create(player=self.player, opportunity=trial, status=status)

    def test_today_is_the_day_email_goes_once_to_shortlisted_players(self):
        shortlisted = self.apply(self.trial(event_date=self.today + timedelta(days=0), deadline=self.today))
        other = make_player('amani@gmail.com', 'Amani Otieno', 'stars')
        Application.objects.create(player=other, opportunity=shortlisted.opportunity, status='pending')
        self.assertEqual(send_trial_day_reminders(self.today), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jack@gmail.com'])
        self.assertIn("Today is the day! Don't be late, Jack", mail.outbox[0].subject)
        self.assertEqual(send_trial_day_reminders(self.today), 0)  # never twice

    def test_first_visit_of_the_day_sends_the_reminders(self):
        from opportunities import reminders
        reminders._last_run['day'] = None
        self.apply(self.trial())  # no trial date: the deadline (today) counts as the day
        self.client.get(reverse('home'))
        self.assertEqual(len(mail.outbox), 1)

    def test_card_changes_with_the_trial_day(self):
        application = self.apply(self.trial(deadline=self.today + timedelta(days=3)))
        self.client.force_login(self.player)
        self.assertContains(self.client.get(reverse('my_applications')), 'Great news!')
        Opportunity.objects.filter(pk=application.opportunity_id).update(deadline=self.today)
        self.assertContains(self.client.get(reverse('my_applications')), 'Today is the day!')
        Opportunity.objects.filter(pk=application.opportunity_id).update(deadline=self.today - timedelta(days=2))
        page = self.client.get(reverse('my_applications'))
        self.assertContains(page, 'Did you attend Elite Midfield Talent Search?')
        self.assertContains(page, 'id="tf-modal"')
        self.assertContains(self.client.get(reverse('player_dashboard')), 'id="tf-modal"')

    def test_player_answers_yes_or_no_with_a_reason(self):
        application = self.apply(self.trial(deadline=self.today - timedelta(days=1)))
        url = reverse('application_attendance', args=[application.id])
        self.client.force_login(self.player)
        self.assertEqual(self.client.post(url, {'attended': 'no'}).status_code, 400)  # needs a reason
        self.assertEqual(self.client.post(url, {'attended': 'no', 'reason': 'other'}).status_code, 400)  # needs a note
        self.assertTrue(self.client.post(url, {'attended': 'no', 'reason': 'transport'}).json()['ok'])
        application.refresh_from_db()
        self.assertEqual((application.attended, application.absence_reason), (False, 'transport'))
        self.assertTrue(self.client.post(url, {'attended': 'yes', 'note': 'I scored!'}).json()['ok'])
        application.refresh_from_db()
        self.assertEqual((application.attended, application.attendance_note, application.absence_reason), (True, 'I scored!', ''))
        page = self.client.get(reverse('my_applications'))
        self.assertContains(page, 'You went!')
        self.assertNotContains(page, 'id="tf-modal"')

    def test_no_answers_before_the_day_or_for_someone_else(self):
        early = self.apply(self.trial(deadline=self.today + timedelta(days=1)))
        self.client.force_login(self.player)
        self.assertEqual(self.client.post(reverse('application_attendance', args=[early.id]), {'attended': 'yes'}).status_code, 400)
        other = make_player('amani@gmail.com', 'Amani Otieno', 'stars')
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('application_attendance', args=[early.id]), {'attended': 'yes'}).status_code, 404)

    def test_trial_date_cannot_be_before_the_deadline(self):
        form = OpportunityForm(data={'title': 'Trials', 'organization': 'Talantafc', 'category': 'open', 'description': 'x',
                                     'location': 'Nairobi', 'deadline': (self.today + timedelta(days=5)).isoformat(),
                                     'event_date': (self.today + timedelta(days=2)).isoformat()}, scout=self.scout)
        self.assertFalse(form.is_valid())
        self.assertIn('event_date', form.errors)
