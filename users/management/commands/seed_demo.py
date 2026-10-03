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
# For the demo: a scout waiting for the admin, and a player under 18 waiting for a parent.
PENDING_SCOUT = ('Coach Lucy Wambui', 'lucy@demo.ke', 'Kibera Girls Soccer Academy', 'starlets')
MINOR = ('Wanjiku Kamau', 'wanjiku@demo.ke', 'starlets', 'Midfielder', 'Nakuru', 15, 'Mary Kamau', 'parent@demo.ke')
DEMO_UPDATE = (
    'Talanta Soka welcomes Stars and Starlets',
    "Football is for everyone! Talanta Soka now celebrates men's and women's football.",
    "Stars (men's football) and Starlets (women's football)\n"
    'Trials marked Stars, Starlets or Open to all\n'
    'Scouts choose whom they scout, checked against their document\n'
    'A Report a concern link on every page',
)


def demo_letter_pdf(organization, coach):
    """A one-page sample letter (clearly marked DEMO), so the admin can open a real document in practice."""
    lines = [f'{organization}', 'Nairobi, Kenya', '', 'To: Talanta Soka verification team', '',
             f'This letter confirms that {coach}', f'is a coach at {organization}', "and scouts players for our women's team.",
             '', 'Signed: Academy Director', '', 'DEMO DOCUMENT - for practice only']
    text = 'BT /F1 16 Tf 72 760 Td 22 TL ' + ' '.join(f'({line}) Tj T*' for line in lines) + ' ET'
    objects = [
        '<< /Type /Catalog /Pages 2 0 R >>',
        '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
        f'<< /Length {len(text)} >>\nstream\n{text}\nendstream',
        '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    ]
    out, offsets = '%PDF-1.4\n', []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f'{number} 0 obj\n{body}\nendobj\n'
    xref = len(out)
    out += f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n' + ''.join(f'{o:010d} 00000 n \n' for o in offsets)
    out += f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'
    return out.encode('latin-1')


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

        from django.core.files.base import ContentFile

        from users.models import SiteUpdate

        name, email, org, scouts_for = PENDING_SCOUT
        user, _ = User.objects.get_or_create(email=email, defaults={'full_name': name, 'role': 'scout'})
        user.set_password(PASSWORD)
        user.is_active = True
        user.save()
        scout = Scout.objects.filter(user=user).first() or Scout(user=user)
        scout.organization, scout.specialization, scout.scouts_for = org, 'general', scouts_for
        scout.verified, scout.verification_status = False, 'pending'
        if not scout.verification_document:
            scout.verification_document.save('lucy-wambui-letter.pdf', ContentFile(demo_letter_pdf(org, name)), save=False)
        scout.save()

        name, email, category, position, county, age, parent, parent_email = MINOR
        user, _ = User.objects.get_or_create(email=email, defaults={'full_name': name, 'role': 'player'})
        user.set_password(PASSWORD)
        user.is_active = True
        user.save()
        born = date(date.today().year - age, 3, 10)
        PlayerProfile.objects.update_or_create(user=user, defaults={
            'full_name': name, 'category': category, 'position': position, 'location': county,
            'date_of_birth': born, 'age': date.today().year - born.year - ((date.today().month, date.today().day) < (born.month, born.day)),
            'guardian_name': parent, 'guardian_email': parent_email, 'guardian_consent_at': timezone.now(),
            'guardian_email_sent_at': timezone.now(), 'guardian_approved_at': None, 'guardian_declined_at': None,
            'bio': f'Starlet from {county}, playing as a {position.lower()}.',
        })

        # Badges for the demo: Grace has Achieng in her Interests and gave her a Fair Play badge.
        from scouts.models import FairPlayAward, ScoutPlayerShortlist
        grace = User.objects.get(email='grace@demo.ke')
        achieng = PlayerProfile.objects.get(user__email='achieng@demo.ke')
        ScoutPlayerShortlist.objects.get_or_create(scout=grace, profile=achieng)
        FairPlayAward.objects.get_or_create(scout=grace, profile=achieng, defaults={'qualities': 'respect,teamwork'})

        title, teaser, points = DEMO_UPDATE
        SiteUpdate.objects.get_or_create(title=title, defaults={'teaser': teaser, 'points': points, 'created_by': admin})

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
            '  grace@demo.ke (scouts Starlets), peter@demo.ke (scouts Stars), amina@demo.ke (scouts both)\n'
            '  lucy@demo.ke (scout waiting for the admin), wanjiku@demo.ke (aged 15, waiting for a parent)'
        ))
