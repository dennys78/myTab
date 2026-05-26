from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

from reconciliation.nav_permissions import default_sidebar_menu


def create_default_profiles(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model('reconciliation', 'UserProfile')
    for user in User.objects.all():
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'sidebar_menu': default_sidebar_menu(user.is_staff or user.is_superuser)},
        )


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reconciliation', '0016_rename_default_company'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sidebar_menu', models.JSONField(blank=True, default=list, verbose_name='Menu laterale')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Profilo utente',
                'verbose_name_plural': 'Profili utente',
            },
        ),
        migrations.RunPython(create_default_profiles, migrations.RunPython.noop),
    ]
