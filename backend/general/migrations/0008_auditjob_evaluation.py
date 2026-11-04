from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("general", "0007_auditjob_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditjob",
            name="evaluation",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
