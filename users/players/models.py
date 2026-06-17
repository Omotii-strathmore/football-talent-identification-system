from django.db import models
from users.models import User

class Player(models.Model):

    full_name = models.CharField(max_length=100)
    age = models.PositiveIntegerField()
    position = models.CharField(max_length=50)
    