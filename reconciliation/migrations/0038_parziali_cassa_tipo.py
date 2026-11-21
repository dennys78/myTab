from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0037_logista_incerto_notifica'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tabaunorequest',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('chiusura', 'Chiusura'),
                    ('preordine_gratta', 'Preordine gratta'),
                    ('preordine_tabacchi', 'Preordine tabacchi'),
                    ('deposita_ordine_logista', 'Deposita Ordine Logista'),
                    ('parziali_cassa', 'Parziali cassa'),
                ],
                default='chiusura',
                max_length=32,
            ),
        ),
    ]
