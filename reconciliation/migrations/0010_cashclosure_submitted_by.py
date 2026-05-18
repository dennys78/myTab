from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0009_acquisitiondraft_acquisitiondraftimage'),
    ]

    operations = [
        migrations.AddField(
            model_name='cashclosure',
            name='submitted_by',
            field=models.CharField(blank=True, max_length=100, verbose_name='Inviato da'),
        ),
    ]
