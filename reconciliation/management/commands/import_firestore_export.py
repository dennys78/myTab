import glob
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reconciliation.firebase_import import import_mapped_closure, map_registrazione_document
from reconciliation.firestore_export import iter_export_documents, prepare_doc_data
from reconciliation.models import Company


class Command(BaseCommand):
    help = (
        'Importa chiusure da un export gestito di Cloud Firestore '
        '(file LevelDB output-*) nella collection registrazioni → myTaba'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--path',
            action='append',
            default=[],
            help='File export output-* (ripetibile). Alternativa a --dir.',
        )
        parser.add_argument(
            '--dir',
            default='',
            help='Cartella export: importa tutti i file *output-* presenti.',
        )
        parser.add_argument(
            '--company',
            default=os.environ.get('FIREBASE_IMPORT_COMPANY', 'Parrot caffè'),
            help='Denominazione azienda myTaba di destinazione (default: Parrot caffè)',
        )
        parser.add_argument(
            '--collection',
            default='registrazioni',
            help='Nome collection/kind da importare (default: registrazioni)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Simula senza scrivere.')
        parser.add_argument('--limit', type=int, default=0, help='Importa al massimo N documenti (0 = tutti).')
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Aggiorna chiusure già importate da Firebase (rigenera i reparti).',
        )

    def _resolve_files(self, options) -> list[str]:
        files: list[str] = list(options.get('path') or [])
        export_dir = (options.get('dir') or '').strip()
        if export_dir:
            if not os.path.isdir(export_dir):
                raise CommandError(f'Cartella non trovata: {export_dir}')
            found = sorted(
                p for p in glob.glob(os.path.join(export_dir, '*output-*'))
                if not p.endswith('.export_metadata')
            )
            files.extend(found)
        files = [f for f in dict.fromkeys(files) if f]
        if not files:
            raise CommandError('Specifica almeno --path <file output-*> oppure --dir <cartella export>.')
        missing = [f for f in files if not os.path.isfile(f)]
        if missing:
            raise CommandError('File non trovati:\n  ' + '\n  '.join(missing))
        return files

    def _resolve_company(self, name: str) -> Company:
        company = Company.objects.filter(denominazione__iexact=name).first()
        if not company:
            company = Company.objects.filter(denominazione__icontains=name).first()
        if not company:
            available = ', '.join(Company.objects.values_list('denominazione', flat=True)[:10])
            raise CommandError(
                f'Azienda non trovata: "{name}". Aziende presenti: {available or "(nessuna)"}'
            )
        return company

    def handle(self, *args, **options):
        files = self._resolve_files(options)
        company = self._resolve_company(options['company'].strip())
        collection = options['collection']
        dry_run = options['dry_run']
        limit = options['limit']
        update_existing = options['update_existing']

        self.stdout.write(f'Azienda destinazione: {company.denominazione}')
        self.stdout.write(f'File export: {len(files)}')
        if dry_run:
            self.stdout.write(self.style.WARNING('Modalità dry-run: nessuna scrittura.'))

        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'invalid': 0, 'dry_run': 0, 'dry_run_updated': 0}
        processed = 0

        with transaction.atomic():
            for path in files:
                with open(path, 'rb') as handle:
                    data = handle.read()
                for doc_id, doc_data in iter_export_documents(data, collection=collection):
                    if limit and processed >= limit:
                        break
                    processed += 1

                    mapped = map_registrazione_document(doc_id, prepare_doc_data(doc_data))
                    if not mapped:
                        stats['invalid'] += 1
                        self.stdout.write(self.style.WARNING(f'  Saltato {doc_id}: dataIncasso mancante o non valida'))
                        continue

                    result = import_mapped_closure(
                        company, mapped, dry_run=dry_run, update_existing=update_existing,
                    )
                    stats[result] = stats.get(result, 0) + 1
                    if processed <= 5 or result in ('created', 'updated'):
                        self.stdout.write(
                            f'  {doc_id} → {mapped["date"]} | reparti: {len(mapped["items"])} | {result}'
                        )
                if limit and processed >= limit:
                    break

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
