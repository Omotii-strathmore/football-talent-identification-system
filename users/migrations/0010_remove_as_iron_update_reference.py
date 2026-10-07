from django.db import migrations


VERSE = 'As iron sharpens iron, so one person sharpens another.'
REFERENCE = 'Proverbs 27:17'


def remove_reference(apps, schema_editor):
    SiteUpdate = apps.get_model('users', 'SiteUpdate')
    SiteUpdate.objects.filter(
        title__istartswith='As iron sharpens iron',
        verse=VERSE,
        verse_ref__iexact=REFERENCE,
    ).update(verse_ref='')


def restore_reference(apps, schema_editor):
    SiteUpdate = apps.get_model('users', 'SiteUpdate')
    SiteUpdate.objects.filter(
        title__istartswith='As iron sharpens iron',
        verse=VERSE,
        verse_ref='',
    ).update(verse_ref=REFERENCE)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0009_admin_notifications'),
    ]

    operations = [
        migrations.RunPython(remove_reference, restore_reference),
    ]
