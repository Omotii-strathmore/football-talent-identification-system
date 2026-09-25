from datetime import date

from django.db import models
from users.models import User


def _calculate_age(born):
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


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
    date_of_birth = models.DateField(
        blank=True,
        null=True,
        help_text='Used to keep your age accurate automatically.'
    )
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
    previous_club_start_year = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Year you joined the previous club, e.g. 2019.'
    )
    previous_club_end_year = models.PositiveIntegerField(
        blank=True,
        null=True,
        help_text='Year you left the previous club, e.g. 2021.'
    )
    special_traits = models.CharField(
        max_length=150,
        blank=True,
        help_text='Examples: Playmaker, Flair, Finesse shooter.'
    )
    football_experience = models.TextField(
        blank=True,
        help_text='Briefly describe your achievements and highlights at your previous club.'
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

    def save(self, *args, **kwargs):
        if self.date_of_birth:
            self.age = _calculate_age(self.date_of_birth)
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add('age')
                kwargs['update_fields'] = update_fields
        super().save(*args, **kwargs)

    def __str__(self):
        return self.full_name


class PlayerVideo(models.Model):

    CATEGORY_CHOICES = (
        ('highlights', 'Highlights'),
        ('match', 'Match Footage'),
        ('training', 'Training'),
        ('skills', 'Skills Showcase'),
    )

    profile = models.ForeignKey(
        PlayerProfile,
        on_delete=models.CASCADE,
        related_name='videos'
    )
    title = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='highlights',
        help_text='Helps scouts quickly understand what this clip shows.'
    )
    description = models.TextField(
        blank=True,
        help_text='Optional: add context such as the match, opponent, or what to look out for.'
    )
    video_file = models.FileField(upload_to='player_videos/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.profile.full_name} - {self.title}'