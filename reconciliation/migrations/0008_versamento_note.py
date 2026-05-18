from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0007_accantonamento_fondocassa'),
    ]

    operations = [
        migrations.AddField(
            model_name='versamento',
            name='note',
            field=models.TextField(blank=True, verbose_name='Note'),
        ),
    ]
