

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_python', '0007_alter_repoenvkey_unique_together_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='UserInputModel',
        ),
    ]
