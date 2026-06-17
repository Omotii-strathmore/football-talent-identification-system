from django.db import models
from users.models import User

class Scout(models.Model):

  organization = models.CharField(max_length=100)

  verified = models.BooleanField(default=False)
 
  def __str__(self):
        return self.organization