from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, full_name='', role='player'):
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        user = self.model(
            email=email,
            full_name=full_name,
            role=role,
        )
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, full_name='Administrator'):
        user = self.create_user(
            email=email,
            password=password,
            full_name=full_name,
            role='scout',
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    ROLE_CHOICES = [
        ('player','Player'),
        ('scout', 'Scout'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='player')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    terms_accepted_at = models.DateTimeField(blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    objects = UserManager()

    def __str__(self):
        return f'{self.full_name} ({self.email})'


class OneTimeCode(models.Model):
    METHOD_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
    ]

    PURPOSE_CHOICES = [
        ('verify', 'Account verification'),
        ('reset', 'Password reset'),
    ]

    user = models.ForeignKey('User', on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=10)
    method = models.CharField(max_length=10, choices=METHOD_CHOICES, default='email')
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES, default='verify')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    used = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['user', 'code'])]

    def __str__(self):
        return f'OTP for {self.user.email} via {self.method} ({self.code})'