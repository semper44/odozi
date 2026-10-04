

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account_profile', '0005_githubrepository'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='workspacemembership',
            old_name='user',
            new_name='members',
        ),
        migrations.AlterUniqueTogether(
            name='workspacemembership',
            unique_together={('members', 'workspace')},
        ),
    ]
