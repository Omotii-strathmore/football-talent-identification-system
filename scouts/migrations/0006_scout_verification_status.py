from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scouts', '0005_scoutvideofeedback_interaction_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='scout',
            name='verification_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
                default='pending',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('scouts', 'Scout').objects.filter(verified=True).update(verification_status='approved'),
            reverse_code=migrations.RunPython.noop,
        ),
    ]
