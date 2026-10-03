from datetime import timedelta

from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from users.models import User
from players.models import PlayerProfile, PlayerVideo

from players.categories import SCOUTS_FOR_CHOICES

class Scout(models.Model):

    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='scout_profile'
    )

    organization = models.CharField(max_length=100)

    specialization = models.CharField(max_length=120)

    verification_document = models.FileField(
        upload_to='scout_verification_docs/',
        validators=[FileExtensionValidator(['pdf', 'doc', 'docx'])]
    )

    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True
    )
    # Which part of the photo shows inside round frames, as "x% y%" (chosen by dragging the photo).
    photo_position = models.CharField(max_length=20, default='50% 30%', blank=True)

    verified = models.BooleanField(default=False)
    # Which football the scout looks for: Stars (men), Starlets (women) or both.
    scouts_for = models.CharField(max_length=10, choices=SCOUTS_FOR_CHOICES, default='both')
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending'
    )
 
    def __str__(self):
        return f'{self.organization} ({self.user.full_name})'


class ScoutPlayerFeedback(models.Model):
    scout = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='player_feedback_entries',
    )
    profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='feedback_entries',
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['scout', 'profile'],
                name='unique_scout_player_feedback',
            )
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.scout.full_name} feedback for {self.profile.full_name}'


class ScoutPlayerShortlist(models.Model):
    scout = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='shortlisted_players',
    )
    profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='shortlisted_by',
    )
    notes = models.TextField(
        blank=True,
        default='',
        help_text='Your private notes about this player.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['scout', 'profile'],
                name='unique_scout_player_shortlist',
            )
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.scout.full_name} interested in {self.profile.full_name}'


class ScoutVideoFeedback(models.Model):
    REACTION_CHOICES = [
        ('', 'No reaction'),
        ('acknowledged', 'Acknowledged'),
        ('interested', 'Interested'),
        ('noted', 'Noted'),
    ]

    REPLY_EDIT_WINDOW_MINUTES = 15

    scout = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='video_feedback_entries',
    )
    video = models.ForeignKey(
        PlayerVideo,
        on_delete=models.CASCADE,
        related_name='video_feedback_entries',
    )
    comment = models.TextField()
    player_reply = models.TextField(blank=True, default='')
    player_reply_at = models.DateTimeField(blank=True, null=True)
    player_reaction = models.CharField(
        max_length=20,
        choices=REACTION_CHOICES,
        blank=True,
        default='',
    )
    scout_reply = models.TextField(blank=True, default='')
    scout_reply_at = models.DateTimeField(blank=True, null=True)
    is_seen = models.BooleanField(default=False)
    seen_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['scout', 'video'],
                name='unique_scout_video_feedback',
            )
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.scout.full_name} feedback for {self.video.title}'

    @property
    def player_reply_editable(self):
        if not self.player_reply_at:
            return False
        return timezone.now() - self.player_reply_at <= timedelta(minutes=self.REPLY_EDIT_WINDOW_MINUTES)

    @property
    def scout_reply_editable(self):
        if not self.scout_reply_at:
            return False
        return timezone.now() - self.scout_reply_at <= timedelta(minutes=self.REPLY_EDIT_WINDOW_MINUTES)

class FairPlayAward(models.Model):
    """A verified scout recognises a player's character: respect, teamwork, discipline, humility, being on time."""

    QUALITY_CHOICES = [
        ('respect', 'Respect'),
        ('teamwork', 'Teamwork'),
        ('discipline', 'Discipline'),
        ('humility', 'Humility'),
        ('on_time', 'On time'),
    ]

    scout = models.ForeignKey(User, on_delete=models.CASCADE, related_name='fair_play_given')
    profile = models.ForeignKey(PlayerProfile, on_delete=models.CASCADE, related_name='fair_play_awards')
    qualities = models.CharField(max_length=120, help_text='Comma-separated quality keys.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['scout', 'profile'], name='unique_fair_play_per_scout')]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.scout.full_name} gave Fair Play to {self.profile.full_name}'

    @property
    def quality_labels(self):
        names = dict(self.QUALITY_CHOICES)
        return [names[key] for key in self.qualities.split(',') if key in names]
