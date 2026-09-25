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

class SiteFeedback(models.Model):
    RATING_CHOICES = [
        ('bad', 'Bad'),
        ('fine', 'Fine'),
        ('good', 'Good'),
    ]
    # Options offered in the popup after each rating; kept here so the view can reject anything else.
    REASON_CHOICES = {
        'bad': [
            ('slow', 'Pages are slow to load'),
            ('error', 'Something did not work or showed an error'),
            ('hard_to_find', 'Hard to find what I need'),
            ('video_upload', 'Problems uploading videos'),
            ('phone', 'Hard to use on my phone'),
            ('few_opportunities', 'Not enough trials or players'),
            ('other', 'Something else'),
        ],
        'fine': [
            ('faster', 'Faster pages'),
            ('simpler', 'Simpler, clearer design'),
            ('more_opportunities', 'More trials or players'),
            ('phone', 'Better on my phone'),
            ('alerts', 'Alerts when something new happens'),
            ('other', 'Something else'),
        ],
        'good': [
            ('easy', 'Easy to use'),
            ('looks', 'It looks great'),
            ('opportunities', 'Finding trials and opportunities'),
            ('videos', 'Showing off my football videos'),
            ('scout_feedback', 'Feedback between players and scouts'),
            ('find_players', 'Finding talented players'),
            ('other', 'Something else'),
        ],
    }

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='site_feedback')
    role = models.CharField(max_length=20, blank=True)
    rating = models.CharField(max_length=10, choices=RATING_CHOICES)
    reasons = models.JSONField(default=list, blank=True)
    comment = models.TextField(blank=True)
    page = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_rating_display()} from {self.user}'

    @property
    def reason_labels(self):
        labels = dict(self.REASON_CHOICES.get(self.rating, []))
        return [labels.get(code, code) for code in self.reasons]
