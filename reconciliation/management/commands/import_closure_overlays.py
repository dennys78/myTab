import json

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_date

from reconciliation.closure_reports import apply_overlays_for_date
from reconciliation.models import Company


class Command(BaseCommand):
    help = (
        'Applica report esterni (Lottomatica, Sisal, Gratta e Vinci) su una chiusura per data. '
        'Sovrascrive i reparti indicati per quella giornata.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--company', required=True, help='Denominazione azienda myTaba')
        parser.add_argument('--date', required=True, help='Data chiusura YYYY-MM-DD')
        parser.add_argument(
            '--from-json',
            default='',
            help='File JSON con chiavi lottomatica/gratta/sisal e sottochiavi entrate/uscite',
        )
        parser.add_argument('--lottomatica-entrate', type=str, default='')
        parser.add_argument('--lottomatica-uscite', type=str, default='')
        parser.add_argument('--gratta-uscite', type=str, default='', help='Totale uscite reparto Gratta e Vinci')
        parser.add_argument('--sisal-entrate', type=str, default='')
        parser.add_argument('--sisal-uscite', type=str, default='')
        parser.add_argument('--mooney-entrate', type=str, default='')
        parser.add_argument('--mooney-uscite', type=str, default='')

    def handle(self, *args, **options):
        company_name = options['company'].strip()
        company = Company.objects.filter(denominazione__iexact=company_name).first()
        if not company:
            company = Company.objects.filter(denominazione__icontains=company_name).first()
        if not company:
            raise CommandError(f'Azienda non trovata: {company_name}')

        closure_date = parse_date(options['date'])
        if not closure_date:
            raise CommandError('Data non valida. Usa YYYY-MM-DD')

        overlays = {}

        if options.get('from_json'):
            path = options['from_json']
            try:
                with open(path, encoding='utf-8') as f:
                    data = json.load(f)
            except OSError as exc:
                raise CommandError(f'File non trovato: {path}') from exc
            except json.JSONDecodeError as exc:
                raise CommandError(f'JSON non valido: {exc}') from exc
            for key in ('lottomatica', 'gratta', 'sisal', 'mooney'):
                block = data.get(key)
                if isinstance(block, dict):
                    overlays[key] = {
                        'entrate': block.get('entrate', 0),
                        'uscite': block.get('uscite', 0),
                    }

        for arg, key in (
            ('lottomatica-entrate', 'lottomatica'),
            ('lottomatica-uscite', 'lottomatica'),
            ('gratta-uscite', 'gratta'),
            ('sisal-entrate', 'sisal'),
            ('sisal-uscite', 'sisal'),
            ('mooney-entrate', 'mooney'),
            ('mooney-uscite', 'mooney'),
        ):
            val = options.get(arg, '').strip()
            if val:
                dept_key, field = key.split('-', 1)[0]
                if dept_key not in overlays:
                    overlays[dept_key] = {'entrate': 0, 'uscite': 0}
                if field == 'entrate':
                    overlays[dept_key]['entrate'] = val
                else:
                    overlays[dept_key]['uscite'] = val

        if not overlays:
            self.stdout.write(self.style.WARNING('Nessun overlay da applicare.'))
            return

        closure = apply_overlays_for_date(company, closure_date, overlays)
        self.stdout.write(self.style.SUCCESS(
            f'Overlay applicati su chiusura {closure_date} ({company.denominazione}). '
            f'Reparti aggiornati: {", ".join(sorted(overlays.keys()))}'
        ))
