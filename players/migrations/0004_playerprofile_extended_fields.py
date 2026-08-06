from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('players', '0003_playerprofile_contact_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='playerprofile',
            name='secondary_position',
            field=models.CharField(blank=True, help_text='Secondary playing position (optional).', max_length=50, choices=[('Goalkeeper', 'Goalkeeper'), ('Defender', 'Defender'), ('Midfielder', 'Midfielder'), ('Forward', 'Forward')]),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='height_cm',
            field=models.PositiveIntegerField(blank=True, help_text='Height in centimeters.', null=True),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='weight_kg',
            field=models.PositiveIntegerField(blank=True, help_text='Weight in kilograms.', null=True),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='current_club',
            field=models.CharField(blank=True, help_text='Current club or academy.', max_length=100),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='special_traits',
            field=models.CharField(blank=True, help_text='Examples: Playmaker, Flair, Finesse shooter.', max_length=150),
        ),
        migrations.AddField(
            model_name='playerprofile',
            name='football_experience',
            field=models.TextField(blank=True, help_text='Describe your football experience, clubs, and achievements.'),
        ),
    ]
