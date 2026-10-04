

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('account_profile', '0014_alter_githubrepository_repo_full_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofilemodel',
            name='installed_github',
            field=models.BooleanField(default=False),
        ),
    ]
