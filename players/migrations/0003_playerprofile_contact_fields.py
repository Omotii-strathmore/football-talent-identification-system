from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0002_playervideo'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerprofile',
            name='consent_to_share_contact',
            field=models.BooleanField(default=False, help_text='Allow scouts to view your communication options.'),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='contact_email',
            field=models.EmailField(blank=True, help_text='Optional email scouts can use to contact you.', max_length=254, null=True),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='contact_phone',
            field=models.CharField(blank=True, help_text='Optional phone number scouts can use to contact you.', max_length=30),
        ),
    ]
