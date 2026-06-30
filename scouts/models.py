from django.db import models
from users.models import User
from players.models import PlayerProfile, PlayerVideo

class Scout(models.Model):

  user = models.OneToOneField(
      User,
      on_delete=models.CASCADE,
      related_name='scout_profile'
  )

  organization = models.CharField(max_length=100)

  specialization = models.CharField(max_length=120)

  verification_document = models.FileField(
      upload_to='scout_verification_docs/'
  )

  profile_photo = models.ImageField(
      upload_to='profile_photos/',
      blank=True,
      null=True
  )

  verified = models.BooleanField(default=False)
 
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


class ScoutVideoFeedback(models.Model):
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