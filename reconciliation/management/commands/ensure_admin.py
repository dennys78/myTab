from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Crea utente admin iniziale da variabili ambiente se non esiste alcun utente'

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write('Utenti già presenti — nessuna azione.')
            return
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '').strip()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    'Nessun utente presente. Imposta DJANGO_SUPERUSER_USERNAME e '
                    'DJANGO_SUPERUSER_PASSWORD per creare automaticamente ladmin.'
                )
            )
            return

        user = User(username=username, email=email, is_staff=True, is_superuser=True)
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(
            f'Creato utente amministratore iniziale: {username}'
        ))
