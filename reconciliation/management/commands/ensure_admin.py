from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea utente admin di default se non esiste alcun utente'

    def handle(self, *args, **options):
        if User.objects.exists():
            self.stdout.write('Utenti già presenti — nessuna azione.')
            return
        user = User(username='admin', is_staff=True, is_superuser=True)
        user.set_password('admin1234')
        user.save()
        self.stdout.write(self.style.SUCCESS(
            '*** Creato utente amministratore: admin / admin1234 — CAMBIA LA PASSWORD! ***'
        ))
