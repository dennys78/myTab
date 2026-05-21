from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0011_cashclosureimage'),
    ]

    operations = [
        migrations.AddField(
            model_name='versamento',
            name='ricorda_promemoria',
            field=models.BooleanField(default=False, verbose_name='Ricorda come promemoria'),
        ),
    ]
