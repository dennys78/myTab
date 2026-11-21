from django.core.management.base import BaseCommand, CommandError

from reconciliation.incassi_parziali import ParzialiError, leggi_parziali, testo_telegram
from reconciliation.models import Company, TabaUnoAgent


class Command(BaseCommand):
    help = 'Legge i parziali di cassa dal PC negozio e stampa il testo Telegram.'

    def add_arguments(self, parser):
        parser.add_argument('--company', type=int, help='ID azienda (default: quella con l\'agente TabaUno)')

    def _company(self, company_id):
        if company_id:
            company = Company.objects.filter(id=company_id).first()
            if not company:
                raise CommandError(f'Azienda {company_id} inesistente.')
            return company
        agente = TabaUnoAgent.objects.select_related('company').order_by('id').first()
        if agente:
            return agente.company
        return Company.objects.order_by('id').first()

    def handle(self, *args, **options):
        company = self._company(options.get('company'))
        if not company:
            raise CommandError('Nessuna azienda disponibile.')
        self.stdout.write(f'Azienda: {company} (id {company.id})')
        try:
            dati = leggi_parziali(company)
        except ParzialiError as exc:
            raise CommandError(exc.messaggio) from exc
        self.stdout.write(testo_telegram(dati))
