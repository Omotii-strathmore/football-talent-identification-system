from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouts', '0004_scoutvideofeedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='scoutvideofeedback',
            name='player_reaction',
            field=models.CharField(blank=True, choices=[('', 'No reaction'), ('acknowledged', 'Acknowledged'), ('interested', 'Interested'), ('noted', 'Noted')], default='', max_length=20),
        ),
        migrations.AddField(
            model_name='scoutvideofeedback',
            name='player_reply',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='scoutvideofeedback',
            name='is_seen',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='scoutvideofeedback',
            name='seen_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
