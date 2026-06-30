from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('opportunities', '0002_opportunity_poster_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='opportunity',
            name='max_applications',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
