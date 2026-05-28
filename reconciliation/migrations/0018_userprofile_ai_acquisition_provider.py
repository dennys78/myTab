from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0017_userprofile_sidebar_menu'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='ai_acquisition_provider',
            field=models.CharField(
                blank=True,
                default='',
                max_length=16,
                verbose_name='Modello IA acquisizione (preferenza operatore)',
            ),
        ),
    ]
