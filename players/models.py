from django.db import models
from users.models import User

class PlayerProfile(models.Model):

    POSITION_CHOICES = (
        ('Goalkeeper', 'Goalkeeper'),
        ('Defender', 'Defender'),
        ('Midfielder', 'Midfielder'),
        ('Forward', 'Forward'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='player_profile'
    )

    full_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES
    )

    location = models.CharField(max_length=100)

    profile_photo = models.ImageField(
        upload_to='profile_photos/',
        blank=True,
        null=True
    )

    bio = models.TextField(
        blank=True,
        help_text="Tell scouts about yourself"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.full_name


class PlayerVideo(models.Model):
    profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    title = models.CharField(max_length=150)
    video_file = models.FileField(upload_to='player_videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.profile.full_name} - {self.title}'