import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconciliation.firebase_import import (
    debug_department_candidates,
    import_mapped_closure,
    map_registrazione_document,
)
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
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Aggiorna chiusure già importate da Firebase (rigenera i reparti)',
        )
        parser.add_argument(
            '--debug-doc',
            default='',
            help='ID documento Firestore da ispezionare (stampa struttura reparti e termina)',
        )
        parser.add_argument(
            '--debug-limit',
            type=int,
            default=3,
            help='Numero max righe diagnostiche da mostrare per --debug-doc',
        )

    def handle(self, *args, **options):
        cred_path = (options['credentials'] or os.environ.get('FIREBASE_CREDENTIALS_PATH', '')).strip()
        if not cred_path:
            cred_path = '/run/secrets/firebase-service-account.json'
        if not os.path.isfile(cred_path):
            raise CommandError(
                f'File credenziali Firebase non trovato: {cred_path}\n'
                '1. Firebase Console → Impostazioni progetto → Account di servizio → Genera nuova chiave privata\n'
                '2. Salva il file come secrets/firebase-service-account.json nella cartella myTab sul Mac\n'
                '3. Riavvia: docker compose up -d --build\n'
                'Oppure: --credentials /percorso/reale/file.json'
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
        update_existing = options['update_existing']
        debug_doc = (options.get('debug_doc') or '').strip()
        debug_limit = max(1, int(options.get('debug_limit') or 3))

        self.stdout.write(
            f'Lettura Firestore → collection "{collection_name}" → azienda "{company.denominazione}"'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('Modalità dry-run: nessuna scrittura.'))

        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'invalid': 0,
            'dry_run': 0,
            'dry_run_updated': 0,
        }
        processed = 0

        if debug_doc:
            snap = db.collection(collection_name).document(debug_doc).get()
            if not snap.exists:
                raise CommandError(f'Documento non trovato: {debug_doc}')
            data = snap.to_dict() or {}
            mapped = map_registrazione_document(snap.id, data)
            candidates = debug_department_candidates(data)

            self.stdout.write(self.style.WARNING(f'Debug documento: {debug_doc}'))
            self.stdout.write(f'Chiavi top-level: {sorted(list(data.keys()))}')
            self.stdout.write(f'Reparti mappati dallo script: {len(mapped["items"]) if mapped else 0}')
            if mapped:
                for item in mapped['items']:
                    self.stdout.write(f'  - {item["descrizione"]}: entrate={item["entrate"]} uscite={item["uscite"]}')
            self.stdout.write(f'Candidati trovati (max {debug_limit}): {len(candidates)}')
            for row in candidates[:debug_limit]:
                self.stdout.write(
                    f'  path={row["path"]} | label={row["label"]} | '
                    f'entrate={row["entrate"]} | uscite={row["uscite"]} | keys={row["keys"]}'
                )
            return

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

                result = import_mapped_closure(
                    company,
                    mapped,
                    dry_run=dry_run,
                    update_existing=update_existing,
                )
                stats[result] = stats.get(result, 0) + 1
                if processed <= 5 or result in ('created', 'updated'):
                    self.stdout.write(
                        f'  {snap.id} → {mapped["date"]} | reparti: {len(mapped["items"])} | {result}'
                    )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Fine. Processati: {processed} | '
            f'creati: {stats.get("created", 0)} | '
            f'aggiornati: {stats.get("updated", 0)} | '
            f'già presenti: {stats.get("skipped", 0)} | '
            f'non validi: {stats.get("invalid", 0)} | '
            f'dry-run nuovi: {stats.get("dry_run", 0)} | '
            f'dry-run aggiornati: {stats.get("dry_run_updated", 0)}'
        ))
