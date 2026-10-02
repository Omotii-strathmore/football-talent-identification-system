import tempfile
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from opportunities.models import Application, Opportunity
from players.categories import can_apply
from players.models import PlayerProfile
from scouts.models import Scout
from users.models import User


def make_player(email, name, category):
    user = User.objects.create_user(email, 'Talanta#2026', full_name=name)
    PlayerProfile.objects.create(user=user, full_name=name, date_of_birth=date(2003, 3, 1), age=23,
                                 position='Forward', location='Nairobi', category=category)
    return user


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class StarsAndStarletsTests(TestCase):
    def setUp(self):
        self.star = make_player('juma@gmail.com', 'Juma Star', 'stars')
        self.starlet = make_player('wanjiru@gmail.com', 'Wanjiru Starlet', 'starlets')
        self.scout_user = User.objects.create_user('coach@gmail.com', 'Talanta#2026', full_name='Coach', role='scout')
        self.scout = Scout.objects.create(user=self.scout_user, organization='Thika Queens Academy', specialization='general',
                                          verified=True, verification_status='approved', scouts_for='starlets',
                                          verification_document=SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf'))
        deadline = timezone.localdate() + timedelta(days=10)
        common = dict(scout=self.scout_user, organization='Thika Queens', description='Trials', location='Thika', deadline=deadline)
        self.starlets_trial = Opportunity.objects.create(title='Starlets U-20 trials', category='starlets', **common)
        self.stars_trial = Opportunity.objects.create(title='Stars U-20 trials', category='stars', **common)
        self.open_trial = Opportunity.objects.create(title='Open futsal tournament', category='open', **common)

    def test_who_can_apply_rule(self):
        self.assertTrue(can_apply('starlets', 'starlets'))
        self.assertTrue(can_apply('stars', 'open'))
        self.assertFalse(can_apply('stars', 'starlets'))

    def test_players_apply_only_within_their_category_or_open(self):
        self.client.force_login(self.star)
        self.client.post(reverse('apply_opportunity', args=[self.starlets_trial.id]), {'motivation': 'I am ready.'})
        self.client.post(reverse('apply_opportunity', args=[self.open_trial.id]), {'motivation': 'I am ready.'})
        self.client.post(reverse('apply_opportunity', args=[self.stars_trial.id]), {'motivation': 'I am ready.'})
        applied = set(Application.objects.filter(player=self.star).values_list('opportunity__title', flat=True))
        self.assertEqual(applied, {'Open futsal tournament', 'Stars U-20 trials'})

    def test_players_without_a_category_are_asked_first(self):
        self.star.player_profile.category = ''
        self.star.player_profile.save()
        self.client.force_login(self.star)
        self.assertContains(self.client.get(reverse('player_dashboard')), 'Stars or')
        response = self.client.post(reverse('apply_opportunity', args=[self.open_trial.id]), {'motivation': 'I am ready.'})
        self.assertRedirects(response, reverse('player_dashboard'), fetch_redirect_response=False)
        self.client.post(reverse('player_set_category'), {'category': 'stars'})
        self.star.player_profile.refresh_from_db()
        self.assertEqual(self.star.player_profile.category, 'stars')

    def test_scouts_see_their_category_first_and_can_see_all(self):
        self.client.force_login(self.scout_user)
        page = self.client.get(reverse('scout_player_directory'))
        self.assertContains(page, 'Wanjiru Starlet')
        self.assertNotContains(page, 'Juma Star<')
        everyone = self.client.get(reverse('scout_player_directory') + '?category=all&position=')
        self.assertContains(everyone, 'Juma Star')
        self.assertContains(everyone, 'Wanjiru Starlet')

    def test_trials_page_filters_and_badges(self):
        page = self.client.get(reverse('public_opportunities') + '?cat=starlets')
        self.assertContains(page, 'Starlets U-20 trials')
        self.assertContains(page, 'Open futsal tournament')
        self.assertNotContains(page, 'Stars U-20 trials')

    def test_registration_asks_stars_or_starlets(self):
        client = self.client_class()
        client.post(reverse('register'), {'full_name': 'New Player', 'email': 'new.player@gmail.com', 'role': 'player',
                                          'password': 'Talanta#2026', 'confirm_password': 'Talanta#2026', 'accept_terms': 'on'})
        step2 = reverse('complete_profile')
        self.assertContains(client.get(step2), 'Which football do you play?')
        data = {'date_of_birth': '2003-03-01', 'position': 'Midfielder', 'location': 'Nairobi'}
        self.assertContains(client.post(step2, data), 'Please choose Stars or Starlets.')
        client.post(step2, {**data, 'category': 'starlets'})
        self.assertEqual(PlayerProfile.objects.get(user__email='new.player@gmail.com').category, 'starlets')

    def test_landing_page_welcomes_stars_and_starlets(self):
        page = self.client.get(reverse('home'))
        self.assertContains(page, 'Stars &amp; Starlets')
        self.assertContains(page, '?cat=starlets')
