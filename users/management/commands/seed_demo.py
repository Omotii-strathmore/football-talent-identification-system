"""Fill a local practice database with demo Stars, Starlets, scouts and trials.

    $env:DATABASE_URL = "sqlite:///practice.sqlite3"; $env:R2_BUCKET_NAME = "off"
    python manage.py migrate
    python manage.py seed_demo
    python manage.py runserver

Refuses to run against anything except a SQLite database, so the live data can never be touched.
Every demo account uses the password Demo#2026.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

PASSWORD = 'Demo#2026'

PLAYERS = [
    ('Achieng Wanjiru', 'achieng@demo.ke', 'starlets', 'Midfielder', 'Kisumu', date(2006, 4, 12)),
    ('Faith Chepkoech', 'faith@demo.ke', 'starlets', 'Forward', 'Uasin Gishu', date(2004, 9, 3)),
    ('Mercy Atieno', 'mercy@demo.ke', 'starlets', 'Goalkeeper', 'Nairobi', date(2003, 1, 22)),
    ('Brian Otieno', 'brian@demo.ke', 'stars', 'Forward', 'Nairobi', date(2004, 6, 30)),
    ('Kevin Mwangi', 'kevin@demo.ke', 'stars', 'Defender', 'Kiambu', date(2002, 11, 8)),
    ('Hassan Ali', 'hassan@demo.ke', 'stars', 'Midfielder', 'Mombasa', date(2005, 2, 14)),
]
SCOUTS = [
    ('Coach Grace Njeri', 'grace@demo.ke', 'Thika Queens Academy', 'starlets'),
    ('Coach Peter Kamau', 'peter@demo.ke', 'Gor Mahia Youth Academy', 'stars'),
    ('Coach Amina Yusuf', 'amina@demo.ke', 'Coast Talent Hub', 'both'),
]
TRIALS = [
    ('Starlets U-20 open trials', 'grace@demo.ke', 'starlets', 'Thika Stadium',
     'Open trials for Starlets aged 15 to 20. Bring boots, shin guards and water. Free entry.'),
    ('Stars U-19 academy trials', 'peter@demo.ke', 'stars', 'Camp Toyoyo, Nairobi',
     'Trials for Stars aged 16 to 19, all positions. Free entry; coaches from the academy will be watching.'),
    ('Coast 5-a-side festival', 'amina@demo.ke', 'open', 'Mombasa Municipal Stadium',
     'A one-day 5-a-side festival open to Stars and Starlets. Teams of five, mixed ages 14 to 22.'),
]


class Command(BaseCommand):
    help = 'Fill a local SQLite practice database with demo Stars, Starlets, scouts and trials.'

    def handle(self, *args, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('seed_demo only runs on a local SQLite practice database, never on the live database.')
        from django.conf import settings
        if getattr(settings, 'USE_R2', False):
            raise CommandError('Switch off live file storage first: $env:R2_BUCKET_NAME = "off"')

        from opportunities.models import Opportunity
        from players.models import PlayerProfile
        from scouts.models import Scout
        from users.models import User

        admin, made = User.objects.get_or_create(email='admin@demo.ke', defaults={'full_name': 'Demo Admin', 'role': 'scout'})
        admin.is_staff = admin.is_superuser = True
        admin.is_active = True
        admin.set_password(PASSWORD)
        admin.save()

        for name, email, category, position, county, born in PLAYERS:
            user, _ = User.objects.get_or_create(email=email, defaults={'full_name': name, 'role': 'player'})
            user.set_password(PASSWORD)
            user.is_active = True
            user.save()
            age = date.today().year - born.year - ((date.today().month, date.today().day) < (born.month, born.day))
            PlayerProfile.objects.update_or_create(user=user, defaults={
                'full_name': name, 'category': category, 'position': position, 'location': county,
                'date_of_birth': born, 'age': age, 'contact_email': email,
                'contact_email_verified_at': timezone.now(), 'consent_to_share_contact': True,
                'guardian_approved_at': timezone.now() if age < 18 else None,
                'bio': f"{'Starlet' if category == 'starlets' else 'Star'} from {county}, playing as a {position.lower()}.",
            })

        for name, email, org, scouts_for in SCOUTS:
            user, _ = User.objects.get_or_create(email=email, defaults={'full_name': name, 'role': 'scout'})
            user.set_password(PASSWORD)
            user.is_active = True
            user.save()
            scout = Scout.objects.filter(user=user).first() or Scout(user=user)
            scout.organization, scout.specialization, scout.scouts_for = org, 'general', scouts_for
            scout.verified, scout.verification_status = True, 'approved'
            if not scout.verification_document:
                # Only a name: nothing is uploaded anywhere.
                scout.verification_document.name = 'scout_verification_docs/demo-licence.pdf'
            scout.save()

        for title, email, category, place, description in TRIALS:
            Opportunity.objects.update_or_create(title=title, defaults={
                'scout': User.objects.get(email=email), 'organization': Scout.objects.get(user__email=email).organization,
                'category': category, 'location': place, 'description': description,
                'deadline': timezone.localdate() + timedelta(days=21), 'is_active': True,
            })

        self.stdout.write(self.style.SUCCESS(
            'Practice data ready. Log in with any of these (password Demo#2026):\n'
            '  admin@demo.ke (admin)\n'
            '  achieng@demo.ke, faith@demo.ke, mercy@demo.ke (Starlets)\n'
            '  brian@demo.ke, kevin@demo.ke, hassan@demo.ke (Stars)\n'
            '  grace@demo.ke (scouts Starlets), peter@demo.ke (scouts Stars), amina@demo.ke (scouts both)'
        ))
