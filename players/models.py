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
    secondary_position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        blank=True,
        help_text='Secondary playing position (optional).'
    )
    height_cm = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Height in centimeters.'
    )
    weight_kg = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Weight in kilograms.'
    )
    current_club = models.CharField(
        max_length=100,
        blank=True,
        help_text='Current club or academy.'
    )
    previous_club = models.CharField(
        max_length=100,
        blank=True,
        help_text='Most recent previous club or academy.'
    )
    previous_club_duration = models.CharField(
        max_length=50,
        blank=True,
        help_text='Duration at previous club, e.g. 7 months or 2 years.'
    )
    special_traits = models.CharField(
        max_length=150,
        blank=True,
        help_text='Examples: Playmaker, Flair, Finesse shooter.'
    )
    football_experience = models.TextField(
        blank=True,
        help_text='Describe your football experience, clubs, and achievements.'
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

    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text='Optional email scouts can use to contact you.'
    )

    contact_phone = models.CharField(
        max_length=30,
        blank=True,
        help_text='Optional phone number scouts can use to contact you.'
    )

    consent_to_share_contact = models.BooleanField(
        default=False,
        help_text='Allow scouts to view your communication options.'
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