from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


COMPANY_MODELS = [
    'cashclosure',
    'department',
    'versamento',
    'movimentocassa',
    'fondocassamovimento',
    'acquisitiondraft',
    'appsetting',
    'banktransaction',
]


def create_default_company(apps, schema_editor):
    Company = apps.get_model('reconciliation', 'Company')
    CompanyMembership = apps.get_model('reconciliation', 'CompanyMembership')
    User = apps.get_model(settings.AUTH_USER_MODEL)

    company, _ = Company.objects.get_or_create(
        denominazione='Azienda predefinita',
        defaults={'indirizzo': '', 'piva': ''},
    )

    for model_name in COMPANY_MODELS:
        Model = apps.get_model('reconciliation', model_name)
        Model.objects.filter(company__isnull=True).update(company=company)

    for user in User.objects.all():
        CompanyMembership.objects.get_or_create(user=user, company=company)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0014_fondocassamovimento_tipo'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('denominazione', models.CharField(max_length=200, verbose_name='Denominazione')),
                ('indirizzo', models.TextField(blank=True, verbose_name='Indirizzo')),
                ('piva', models.CharField(blank=True, max_length=16, verbose_name='PIVA')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Azienda',
                'verbose_name_plural': 'Aziende',
                'ordering': ['denominazione', 'id'],
            },
        ),
        migrations.CreateModel(
            name='CompanyMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='memberships', to='reconciliation.company')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='company_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Appartenenza azienda',
                'verbose_name_plural': 'Appartenenze azienda',
                'unique_together': {('user', 'company')},
            },
        ),
        migrations.AlterField(
            model_name='department',
            name='name',
            field=models.CharField(max_length=150, verbose_name='Nome Reparto'),
        ),
        migrations.AlterField(
            model_name='appsetting',
            name='key',
            field=models.CharField(max_length=100),
        ),
        migrations.AddField(
            model_name='cashclosure',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='closures', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='department',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='departments', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='versamento',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='versamenti', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='movimentocassa',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='movimenti_cassa', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='fondocassamovimento',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='fondo_movimenti', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='acquisitiondraft',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='acquisition_drafts', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='appsetting',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AddField(
            model_name='banktransaction',
            name='company',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bank_transactions', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.RunPython(create_default_company, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='cashclosure',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='closures', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='department',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='departments', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='versamento',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versamenti', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='movimentocassa',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimenti_cassa', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='fondocassamovimento',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fondo_movimenti', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='acquisitiondraft',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acquisition_drafts', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='appsetting',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='settings', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterField(
            model_name='banktransaction',
            name='company',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bank_transactions', to='reconciliation.company', verbose_name='Azienda'),
        ),
        migrations.AlterUniqueTogether(
            name='department',
            unique_together={('company', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='appsetting',
            unique_together={('company', 'key')},
        ),
    ]
