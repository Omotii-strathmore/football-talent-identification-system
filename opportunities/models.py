from django.conf import settings
from django.db import models


from players.categories import OPPORTUNITY_CATEGORY_CHOICES

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
	# The day the trial or tournament happens. Optional: when empty, the application deadline counts as the day.
	event_date = models.DateField(blank=True, null=True)
	max_applications = models.PositiveIntegerField(blank=True, null=True)
	# Stars (men), Starlets (women) or open to all players.
	category = models.CharField(max_length=10, choices=OPPORTUNITY_CATEGORY_CHOICES, default='open')
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.title} - {self.organization}'

	@property
	def trial_day(self):
		return self.event_date or self.deadline


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

	# After the trial day, shortlisted players tell us whether they went.
	ABSENCE_CHOICES = [
		('transport', 'Transport or fare was a problem'),
		('school_work', 'School, exams or work'),
		('injury', 'Injured or unwell'),
		('family', 'Family reasons'),
		('cancelled', 'The event was cancelled or moved'),
		('late_news', 'I saw the news too late'),
		('other', 'Other'),
	]
	attended = models.BooleanField(blank=True, null=True)
	absence_reason = models.CharField(max_length=20, choices=ABSENCE_CHOICES, blank=True, default='', db_default='')
	attendance_note = models.TextField(blank=True, default='', db_default='')
	attendance_answered_at = models.DateTimeField(blank=True, null=True)
	# The "Today is the day" email, sent once on the trial day.
	reminder_sent_at = models.DateTimeField(blank=True, null=True)

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

