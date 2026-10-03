from django.core.management.base import BaseCommand

from opportunities.reminders import send_trial_day_reminders


class Command(BaseCommand):
    help = 'Email "Today is the day" reminders to players shortlisted for a trial happening today.'

    def handle(self, *args, **options):
        self.stdout.write(f'Sent {send_trial_day_reminders()} reminder(s).')
