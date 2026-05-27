import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconciliation.firebase_import import map_registrazione_document, import_mapped_closure
from reconciliation.models import Company


class Command(BaseCommand):
    help = 'Importa chiusure da Cloud Firestore (collection registrazioni) in myTaba'

    def add_arguments(self, parser):
        parser.add_argument(
            '--credentials',
            default=os.environ.get('FIREBASE_CREDENTIALS_PATH', ''),
            help='Percorso al file JSON service account Firebase',
        )
        parser.add_argument(
            '--company',
            default=os.environ.get('FIREBASE_IMPORT_COMPANY', 'Parrot caffè'),
            help='Denominazione azienda myTaba di destinazione (default: Parrot caffè)',
        )
        parser.add_argument(
            '--collection',
            default='registrazioni',
            help='Nome collection Firestore (default: registrazioni)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simula senza scrivere sul database',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='Importa al massimo N documenti (0 = tutti)',
        )

    def handle(self, *args, **options):
        cred_path = (options['credentials'] or '').strip()
        if not cred_path or not os.path.isfile(cred_path):
            raise CommandError(
                'Specifica --credentials /path/to/serviceAccount.json '
                'oppure imposta FIREBASE_CREDENTIALS_PATH nel file .env'
            )

        company_name = options['company'].strip()
        company = Company.objects.filter(denominazione__iexact=company_name).first()
        if not company:
            company = Company.objects.filter(denominazione__icontains=company_name).first()
        if not company:
            available = ', '.join(Company.objects.values_list('denominazione', flat=True)[:10])
            raise CommandError(
                f'Azienda non trovata: "{company_name}". '
                f'Aziende presenti: {available or "(nessuna)"}'
            )

        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
        except ImportError as exc:
            raise CommandError(
                'Installa firebase-admin: pip install firebase-admin'
            ) from exc

        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        collection_name = options['collection']
        dry_run = options['dry_run']
        limit = options['limit']

        self.stdout.write(
            f'Lettura Firestore → collection "{collection_name}" → azienda "{company.denominazione}"'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('Modalità dry-run: nessuna scrittura.'))

        stats = {'created': 0, 'skipped': 0, 'invalid': 0, 'dry_run': 0}
        processed = 0

        docs = db.collection(collection_name).stream()
        with transaction.atomic():
            for snap in docs:
                if limit and processed >= limit:
                    break
                processed += 1
                data = snap.to_dict() or {}
                mapped = map_registrazione_document(snap.id, data)
                if not mapped:
                    stats['invalid'] += 1
                    self.stdout.write(self.style.WARNING(f'  Saltato {snap.id}: dataIncasso mancante o non valida'))
                    continue

                result = import_mapped_closure(company, mapped, dry_run=dry_run)
                stats[result] = stats.get(result, 0) + 1
                if processed <= 5 or result == 'created':
                    self.stdout.write(
                        f'  {snap.id} → {mapped["date"]} | reparti: {len(mapped["items"])} | {result}'
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Fine. Processati: {processed} | '
            f'creati: {stats.get("created", 0)} | '
            f'già presenti: {stats.get("skipped", 0)} | '
            f'non validi: {stats.get("invalid", 0)} | '
            f'dry-run: {stats.get("dry_run", 0)}'
        ))
