import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from opportunities.models import Application, Opportunity
from players.badges import player_badges, scout_badges
from players.models import PlayerVideo
from players.test_categories import make_player
from scouts.models import FairPlayAward, Scout, ScoutPlayerFeedback, ScoutPlayerShortlist, ScoutVideoFeedback
from users.models import User


def earned(profile):
    return {badge['key'] for badge in player_badges(profile) if badge['earned']}


def add_video(profile, title='Clip'):
    return PlayerVideo.objects.create(profile=profile, title=title,
                                      video_file=SimpleUploadedFile('c.mp4', b'00', content_type='video/mp4'))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BadgeTests(TestCase):
    def setUp(self):
        self.player = make_player('achieng@gmail.com', 'Achieng Wanjiru', 'starlets')
        self.profile = self.player.player_profile
        self.star = make_player('brian@gmail.com', 'Brian Otieno', 'stars')
        self.scout_user = User.objects.create_user('grace@gmail.com', 'Talanta#2026', full_name='Coach Grace', role='scout')
        Scout.objects.create(user=self.scout_user, organization='Thika Queens Academy', specialization='general',
                             verified=True, verification_status='approved', scouts_for='starlets',
                             verification_document=SimpleUploadedFile('d.pdf', b'%PDF-1.4', content_type='application/pdf'))

    def test_badges_are_earned_by_effort(self):
        self.assertEqual(earned(self.profile), {'pioneer'})
        self.profile.bio = 'Midfielder from Kisumu.'
        self.profile.profile_photo = SimpleUploadedFile('p.jpg', b'x', content_type='image/jpeg')
        self.profile.save()
        first = add_video(self.profile)
        self.assertIn('ready', earned(self.profile))
        add_video(self.profile)
        self.assertNotIn('reel', earned(self.profile))
        add_video(self.profile)
        self.assertIn('reel', earned(self.profile))
        deadline = timezone.localdate() + timedelta(days=5)
        trial = Opportunity.objects.create(scout=self.scout_user, title='Starlets trials', organization='Thika Queens',
                                           description='Trials', location='Thika', deadline=deadline, category='starlets')
        Application.objects.create(player=self.player, opportunity=trial)
        self.assertIn('first_step', earned(self.profile))
        # Good Listener needs replies to 3 pieces of scout feedback.
        for number in range(3):
            video = first if number == 0 else add_video(self.profile, f'Clip {number}')
            ScoutVideoFeedback.objects.create(scout=self.scout_user, video=video, comment='Good movement',
                                              player_reply='Thank you coach' if number < 2 else '')
        self.assertNotIn('listener', earned(self.profile))
        feedback = ScoutVideoFeedback.objects.filter(player_reply='').first()
        feedback.player_reply = 'I will work on it'
        feedback.save()
        self.assertIn('listener', earned(self.profile))

    @override_settings(PIONEER_UNTIL='2020-01-01')
    def test_pioneer_is_only_for_the_first_season(self):
        self.player.terms_accepted_at = timezone.now()
        self.player.save()
        self.assertNotIn('pioneer', earned(self.profile))

    def test_fair_play_only_for_players_the_scout_has_dealt_with(self):
        self.client.force_login(self.scout_user)
        url = reverse('scout_award_fair_play')
        self.client.post(url, {'profile_id': self.profile.id, 'qualities': ['respect']})
        self.assertFalse(FairPlayAward.objects.exists())
        ScoutPlayerShortlist.objects.create(scout=self.scout_user, profile=self.profile)
        self.client.post(url, {'profile_id': self.profile.id})  # no quality chosen
        self.assertFalse(FairPlayAward.objects.exists())
        self.client.post(url, {'profile_id': self.profile.id, 'qualities': ['respect', 'teamwork', 'made-up']})
        award = FairPlayAward.objects.get()
        self.assertEqual(award.quality_labels, ['Respect', 'Teamwork'])
        self.assertIn('fair_play', earned(self.profile))
        self.client.post(url, {'profile_id': self.profile.id, 'qualities': ['humility']})
        self.assertEqual(FairPlayAward.objects.get().quality_labels, ['Humility'])
        self.client.post(url, {'profile_id': self.profile.id, 'action': 'withdraw'})
        self.assertFalse(FairPlayAward.objects.exists())

    def test_scouts_cannot_award_players_outside_their_category(self):
        self.client.force_login(self.scout_user)
        response = self.client.post(reverse('scout_award_fair_play'),
                                    {'profile_id': self.star.player_profile.id, 'qualities': ['respect']})
        self.assertEqual(response.status_code, 404)

    def test_player_sees_badges_and_the_good_news(self):
        ScoutPlayerFeedback.objects.create(scout=self.scout_user, profile=self.profile, comment='Great attitude')
        FairPlayAward.objects.create(scout=self.scout_user, profile=self.profile, qualities='respect,on_time')
        self.client.force_login(self.player)
        page = self.client.get(reverse('player_dashboard'))
        self.assertContains(page, 'My badges')
        self.assertContains(page, 'Coach Grace gave you a <strong>Fair Play</strong> badge for Respect, On time')
        self.assertContains(page, 'Highlight Reel')  # still to earn, shown faded with how to earn it

    def test_directory_shows_badges_and_filters_fair_play(self):
        other = make_player('mercy@gmail.com', 'Mercy Atieno', 'starlets')
        FairPlayAward.objects.create(scout=self.scout_user, profile=self.profile, qualities='respect')
        self.client.force_login(self.scout_user)
        page = self.client.get(reverse('scout_player_directory'))
        self.assertContains(page, 'Fair Play')
        self.assertContains(page, 'Mercy Atieno')
        only = self.client.get(reverse('scout_player_directory'), {'fair_play': '1'})
        self.assertContains(only, 'Achieng Wanjiru')
        self.assertNotContains(only, other.full_name)

    def test_helpful_scout_after_feedback_to_ten_players(self):
        self.assertFalse(scout_badges(self.scout_user)[0]['earned'])
        for number in range(10):
            user = make_player(f'p{number}@gmail.com', f'Player {number}', 'starlets')
            ScoutPlayerFeedback.objects.create(scout=self.scout_user, profile=user.player_profile, comment='Keep going')
        self.assertTrue(scout_badges(self.scout_user)[0]['earned'])
        self.client.force_login(self.scout_user)
        self.assertContains(self.client.get(reverse('scout_dashboard')), 'Helpful Scout')


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PlayerDashboardTests(TestCase):
    def test_one_player_is_a_star_and_sees_scout_feedback(self):
        player = make_player('jack@gmail.com', 'Jack Sese', 'stars')
        scout = User.objects.create_user('peter@gmail.com', 'Talanta#2026', full_name='Coach Peter', role='scout')
        video = add_video(player.player_profile, 'Goals vs Kibera')
        ScoutVideoFeedback.objects.create(scout=scout, video=video, comment='Calm finishing, keep it up')
        self.client.force_login(player)
        page = self.client.get(reverse('player_dashboard')).content.decode()
        self.assertIn('\u2b50 Star</span>', page)
        self.assertNotIn('\u2b50 Stars</span>', page)
        self.assertIn('Calm finishing, keep it up', page)
        self.assertIn('Profile strength', page)
