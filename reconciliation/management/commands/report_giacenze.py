from django.core.management.base import BaseCommand, CommandError

from reconciliation.giacenze_report import esegui_report
from reconciliation.models import Company, TabaUnoAgent
from reconciliation.n8n_tabacchi_views import _attendi_lettura


class Command(BaseCommand):
    help = 'Genera il report giornaliero giacenze e stampa i messaggi HTML (senza invio Telegram).'

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
        status, body = esegui_report(company, attendi_lettura=_attendi_lettura)
        if status != 200:
            self.stderr.write(self.style.ERROR(f"Errore {status}: {body.get('errore', '')}"))
        for i, messaggio in enumerate(body.get('messaggi') or [], start=1):
            self.stdout.write(f'--- messaggio {i} ---')
            self.stdout.write(messaggio)
            self.stdout.write('')
        if status != 200:
            raise CommandError(body.get('errore') or 'Report non disponibile')
