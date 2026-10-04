

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_python', '0002_repositoryscan'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='repositoryscan',
            name='user',
        ),
    ]
