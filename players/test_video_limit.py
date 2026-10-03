from types import SimpleNamespace

from django import forms
from django.test import SimpleTestCase

from players.forms import PlayerVideoForm

MB = 1024 * 1024


class VideoSizeLimitTests(SimpleTestCase):
    """Players often upload on mobile data, so videos are capped at 75MB."""

    def _check(self, size):
        form = PlayerVideoForm()
        form.cleaned_data = {'video_file': SimpleNamespace(size=size)}
        return form.clean_video_file()

    def test_videos_up_to_75mb_are_accepted(self):
        self.assertIsNotNone(self._check(75 * MB))

    def test_bigger_videos_get_a_friendly_message(self):
        with self.assertRaisesMessage(forms.ValidationError, 'under 75MB'):
            self._check(75 * MB + 1)
