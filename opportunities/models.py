from django.conf import settings
from django.db import models


class Opportunity(models.Model):
	scout = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='posted_opportunities',
	)
	title = models.CharField(max_length=150)
	organization = models.CharField(max_length=150)
	description = models.TextField()
	poster_image = models.ImageField(upload_to='opportunity_posters/', blank=True, null=True)
	location = models.CharField(max_length=120)
	deadline = models.DateField()
	max_applications = models.PositiveIntegerField(blank=True, null=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.title} - {self.organization}'


class Application(models.Model):
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('shortlisted', 'Shortlisted'),
		('rejected', 'Rejected'),
	]

	opportunity = models.ForeignKey(
		Opportunity,
		on_delete=models.CASCADE,
		related_name='applications',
	)
	player = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='opportunity_applications',
	)
	motivation = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	applied_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-applied_at']
		constraints = [
			models.UniqueConstraint(
				fields=['opportunity', 'player'],
				name='unique_player_opportunity_application',
			)
		]

	def __str__(self):
		return f'{self.player.email} -> {self.opportunity.title}'

