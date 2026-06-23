from django.db import models
from users.models import User

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