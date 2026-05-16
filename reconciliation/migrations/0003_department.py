from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reconciliation', '0002_remove_cashclosure_calculated_balance_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Department',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, unique=True, verbose_name='Nome Reparto')),
            ],
            options={
                'verbose_name': 'Reparto',
                'verbose_name_plural': 'Reparti',
                'ordering': ['name'],
            },
        ),
    ]
