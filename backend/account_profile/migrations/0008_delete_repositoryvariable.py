

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('account_profile', '0007_repositoryvariable'),
    ]

    operations = [
        migrations.DeleteModel(
            name='RepositoryVariable',
        ),
    ]
