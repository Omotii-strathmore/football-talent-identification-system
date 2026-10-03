from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from users.models import SiteUpdate, UpdateReceipt, User
from users.updates import unsubscribe_token


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', UPDATE_EMAILS_IN_BACKGROUND=False)
class SiteUpdateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin@example.com', 'Talanta#2026', full_name='Admin')
        self.admin.is_staff = True
        self.admin.save()
        self.player = User.objects.create_user('amani@example.com', 'Talanta#2026', full_name='Amani Otieno', role='player')
        self.scout = User.objects.create_user('coach@example.com', 'Talanta#2026', full_name='Otieno Coach', role='scout')
        self.quiet = User.objects.create_user('quiet@example.com', 'Talanta#2026', full_name='Quiet One')
        self.quiet.updates_opt_out = True
        self.quiet.save()
        self.unverified = User.objects.create_user('new@example.com', 'Talanta#2026', full_name='Not Verified')
        self.unverified.is_active = False
        self.unverified.save()

    def publish(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_updates'), {
            'title': 'Safer sign-up', 'teaser': 'Big changes this week.',
            'points': 'Parents approve under-18s\n- Eye button for passwords\n\nLight mode',
        })
        self.client.logout()
        return SiteUpdate.objects.get()

    def test_publishing_emails_only_active_subscribed_users(self):
        update = self.publish()
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['amani@example.com', 'coach@example.com'])
        email = mail.outbox[0]
        self.assertIn("What's New", email.subject)
        html = email.alternatives[0][0]
        self.assertIn(f'/?update={update.pk}', html)
        self.assertIn('/updates/unsubscribe/', html)
        self.assertEqual(update.point_list, ['Parents approve under-18s', 'Eye button for passwords', 'Light mode'])

    def test_pop_up_shows_once_then_never_again(self):
        update = self.publish()
        self.client.force_login(self.player)
        self.assertContains(self.client.get(reverse('home')), 'id="ts-update"')
        self.assertNotContains(self.client.get(reverse('home')), 'data-defer="1"')  # opens straight away
        self.client.post(reverse('update_seen', args=[update.pk]))
        # Afterwards it no longer opens by itself; the landing page only offers it after the tour,
        # once per browser.
        self.assertContains(self.client.get(reverse('home')), 'data-defer="1"')

    def test_email_link_opens_pop_up_on_landing_page(self):
        update = self.publish()
        response = self.client.get(reverse('home') + f'?update={update.pk}')
        self.assertContains(response, 'Safer sign-up')
        self.assertContains(response, 'id="ts-update"')

    def test_people_who_join_later_are_not_emailed_but_see_it_after_the_tour(self):
        self.publish()
        later = User.objects.create_user('later@example.com', 'Talanta#2026', full_name='Later User')
        self.assertFalse(UpdateReceipt.objects.filter(user=later).exists())
        self.client.force_login(later)
        self.assertContains(self.client.get(reverse('home')), 'data-defer="1"')

    def test_new_visitors_get_the_latest_update_after_the_tour(self):
        self.publish()
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Safer sign-up')
        self.assertContains(response, 'data-defer="1"')

    def test_unsubscribe_needs_a_click_and_can_be_undone(self):
        url = reverse('updates_unsubscribe', args=[unsubscribe_token(self.player)])
        self.client.get(url)
        self.player.refresh_from_db()
        self.assertFalse(self.player.updates_opt_out)
        self.client.post(url, {'action': 'unsubscribe'})
        self.player.refresh_from_db()
        self.assertTrue(self.player.updates_opt_out)
        self.client.post(url, {'action': 'resubscribe'})
        self.player.refresh_from_db()
        self.assertFalse(self.player.updates_opt_out)
        self.assertEqual(self.client.get(reverse('updates_unsubscribe', args=['forged'])).status_code, 404)

    def test_user_and_admin_can_resend_an_update(self):
        update = self.publish()
        mail.outbox.clear()
        UpdateReceipt.objects.filter(user=self.player).update(emailed_at=None)
        self.client.force_login(self.player)
        self.assertTrue(self.client.post(reverse('update_email_me', args=[update.pk])).json()['ok'])
        self.assertEqual(mail.outbox[-1].to, ['amani@example.com'])
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_update_send_one', args=[update.pk]), {'email': 'coach@example.com'})
        self.assertEqual(mail.outbox[-1].to, ['coach@example.com'])


class PasswordBoxTests(TestCase):
    def test_login_page_is_never_cached_and_uses_eye_button(self):
        response = self.client.get(reverse('login'))
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(response, 'data-no-autofill')
        self.assertContains(response, 'js/password-eye.js')
        self.assertNotContains(response, 'toggle-login-password')


class TemplateNoteTests(TestCase):
    def test_programmer_notes_never_show_on_pages(self):
        """Django only hides {# ... #} notes written on one line; longer notes must use {% comment %}."""
        import pathlib
        from django.conf import settings
        bad = []
        for path in pathlib.Path(settings.BASE_DIR, 'templates').rglob('*.html'):
            for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                if '{#' in line and '#}' not in line:
                    bad.append(f'{path.name}:{number}')
        self.assertEqual(bad, [])


class WaitingPopUpTests(TestCase):
    def test_a_waiting_pop_up_never_covers_the_page(self):
        """A pop-up waiting for the tour must be truly hidden, or it blocks every button on the landing page."""
        SiteUpdate.objects.create(title='New', teaser='Teaser', points='One')
        page = self.client.get(reverse('home')).content.decode()
        self.assertIn('data-defer="1" hidden', page)
        self.assertIn('.ts-update[hidden]{display:none!important}', page)
        self.assertIn('.ts-update:not(.is-open){pointer-events:none}', page)


class UpdatesViewerAndAboutTests(TestCase):
    def test_feed_lists_updates_newest_first(self):
        SiteUpdate.objects.create(title='First', teaser='a', points='One')
        SiteUpdate.objects.create(title='Second', teaser='b', points='Two\nThree')
        data = self.client.get(reverse('updates_feed')).json()
        self.assertEqual([u['title'] for u in data['updates']], ['Second', 'First'])
        self.assertEqual(data['updates'][0]['points'], ['Two', 'Three'])
        self.assertTrue(data['updates'][0]['recent'])

    def test_landing_page_has_viewer_home_menu_and_about(self):
        page = self.client.get(reverse('home'))
        self.assertContains(page, 'id="tsv"')
        self.assertContains(page, 'id="home-sub"')
        self.assertContains(page, 'data-open-updates')
        self.assertContains(page, reverse('about'))

    def test_about_page_in_english_and_swahili(self):
        page = self.client.get(reverse('about'))
        self.assertContains(page, 'ambitious, driven BBIT students')
        self.assertContains(page, 'Hadithi yetu')
        self.assertContains(page, 'kucheza kwa vumbi')
        self.assertContains(page, 'Stars &amp; Starlets')
