from django.core.management.base import BaseCommand, CommandError

from reconciliation import logista_telegram
from reconciliation.logista_service import n8n_tabacchi_config
from reconciliation.models import Company, TabaUnoAgent

TESTO = '🧪 Test notifica ordine Logista'


class Command(BaseCommand):
    help = 'Invia un messaggio di prova sul canale Telegram usato dai job Logista e stampa l\'esito.'

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
        self.stdout.write(f'Azienda: {company} (id {company.id if company else "-"})')
        esito = logista_telegram.notifica(company, TESTO, etichetta='prova')
        self.stdout.write(f"Token bot: {esito['fonte_token'] or 'ASSENTE'}")
        self.stdout.write(f"Chat: {esito['chat']} ({esito['fonte_chat'] or '-'})")
        for tentativo in esito['tentativi']:
            self.stdout.write(
                f"  chat {tentativo['chat']} {tentativo['metodo']}: "
                f"{'OK' if tentativo['ok'] else 'FALLITA'} HTTP {tentativo['http'] or '-'} {tentativo['dettaglio']}"
            )
        n8n_url, _ = n8n_tabacchi_config()
        self.stdout.write(f"Webhook n8n tabacchi: {'impostato' if n8n_url else 'non impostato'}")
        if esito['ok']:
            self.stdout.write(self.style.SUCCESS(f"Notifica consegnata a {esito['consegnate']} chat."))
        else:
            raise CommandError(f"Notifica NON consegnata: {esito.get('motivo', 'motivo sconosciuto')}")
