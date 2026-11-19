import base64
import io
import hashlib
import json
import tempfile
import urllib.error
import urllib.parse
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.utils import timezone

from reconciliation.logista_service import notifica_n8n
from reconciliation.models import (
    Company,
    LogistaInvioJob,
    TabacchiPreordine,
    TabacchiPreordineRiga,
    TabaUnoAgent,
    TabaUnoRequest,
)

TOKEN = 'token-n8n-tabacchi'
WEBHOOK = 'http://n8n.test/webhook/tabacchi-logista'
ENV = {
    'LOGISTA_SERVICE_URL': 'http://logista.test:3501',
    'LOGISTA_SERVICE_KEY': 'chiave-logista',
    'N8N_TABACCHI_WEBHOOK_URL': WEBHOOK,
    'N8N_TABACCHI_TOKEN': TOKEN,
    'N8N_GRATTA_TOKEN': '',
    'TELEGRAM_BOT_TOKEN': '',
}


def _ok():
    response = MagicMock()
    response.read.return_value = b'{}'
    response.status = 200
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _json_ok(data):
    response = _ok()
    response.read.return_value = json.dumps(data).encode()
    return response


def _lettura_payload():
    ultimo = date(2026, 11, 16)
    aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 14)]
    return {
        'ultimo_giorno_chiuso': ultimo.isoformat(),
        'giorni_apertura': aperture,
        'letto_alle': '2026-11-17T10:00:00+01:00',
        'articoli': [{
            'aams': '201',
            'descrizione': 'CHESTERFIELD BLUE KS DA 20 A.',
            'categoria': 'SIGARETTE',
            'prezzo': 5.8,
            'prezzo_kg': 290,
            'minimo_grammi': 200,
            'giacenza': 20,
            'vendite_giornaliere': {day: 8 for day in aperture},
            'giacenze_fine_giorno': {},
        }],
    }


class _Base(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria n8n')
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)

    def _agente(self, online=True):
        return TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'agent').hexdigest(),
            last_seen=timezone.now() if online else timezone.now() - timedelta(hours=1),
        )

    def _preordine(self):
        lettura = TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
            status=TabaUnoRequest.DONE,
            payload=_lettura_payload(),
        )
        preordine = TabacchiPreordine.objects.create(
            company=self.company,
            request=lettura,
            data_consegna=timezone.localdate() + timedelta(days=5),
            kg=Decimal('1.800'),
            totale=Decimal('522.00'),
        )
        TabacchiPreordineRiga.objects.create(
            preordine=preordine, aams='201', unita=9, kg_per_unita=Decimal('0.200'), famiglia='Sigarette',
        )
        TabacchiPreordineRiga.objects.create(
            preordine=preordine, aams='T5000', unita=4, kg_per_unita=0, famiglia='Dispositivi',
        )
        return preordine


@patch.dict('os.environ', ENV)
class NotificaN8nTests(_Base):
    def _job(self, **campi):
        return LogistaInvioJob.objects.create(
            company=self.company, preordine=self._preordine(), righe_inviate=2, **campi,
        )

    def test_inviato_con_foto(self):
        foto = b'\xff\xd8jpeg'
        with override_settings(MEDIA_ROOT=self.media.name):
            job = self._job(
                stato=LogistaInvioJob.INVIATO,
                origine=LogistaInvioJob.ORIGINE_TELEGRAM,
                codice_ordine='ORD-9',
                data_consegna_logista='23/11/2026',
                foto_invio_path='logista/1_invio.jpg',
                risultato={
                    'esito': 'caricato', 'inserite': 2, 'rifiutate': [], 'avvisi': [],
                    'proposta': {'tabacchi': 1, 'altri': 1, 'testo': 'x'},
                    'invio': {'esito': 'inviato', 'totali': ['Totale 522,00']},
                },
            )
            (self.media_path() / 'logista').mkdir(parents=True)
            (self.media_path() / 'logista' / '1_invio.jpg').write_bytes(foto)
            with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
                self.assertTrue(notifica_n8n(job)['ok'])
        richiesta = urlopen.call_args[0][0]
        self.assertEqual(richiesta.full_url, WEBHOOK)
        self.assertEqual(richiesta.get_header('X-api-key'), TOKEN)
        self.assertEqual(urlopen.call_args[1]['timeout'], 20)
        body = json.loads(richiesta.data)
        self.assertEqual(body['evento'], 'logista_caricato')
        self.assertEqual(body['stato'], 'inviato')
        self.assertEqual(body['codice_ordine'], 'ORD-9')
        self.assertEqual(body['totali'], ['Totale 522,00'])
        self.assertEqual(body['origine'], 'telegram')
        self.assertEqual(body['inserite'], 2)
        self.assertEqual(body['proposta'], {'tabacchi': 1, 'altri': 1})
        self.assertEqual(body['kg_tabacco'], 1.8)
        self.assertEqual(body['pezzi_altri'], 4)
        self.assertEqual(body['valore_stimato'], 522.0)
        self.assertEqual(base64.b64decode(body['foto_jpeg_base64']), foto)
        self.assertNotIn('errore', body)
        self.assertNotIn('righe_presenti', body)

    def media_path(self):
        from pathlib import Path
        return Path(self.media.name)

    def test_attesa_conferma_ed_errore(self):
        attesa = self._job(stato=LogistaInvioJob.ATTESA_CONFERMA, righe_presenti=7)
        with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
            notifica_n8n(attesa)
        body = json.loads(urlopen.call_args[0][0].data)
        self.assertEqual(body['righe_presenti'], 7)
        self.assertNotIn('foto_jpeg_base64', body)
        errore = self._job(stato=LogistaInvioJob.ERRORE, errore='WebT non risponde')
        with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
            notifica_n8n(errore)
        self.assertEqual(json.loads(urlopen.call_args[0][0].data)['errore'], 'WebT non risponde')

    def test_errore_due_tentativi_solo_log(self):
        job = self._job(stato=LogistaInvioJob.ERRORE, errore='x')
        with patch('urllib.request.urlopen', side_effect=urllib.error.URLError('refused')) as urlopen, \
                self.assertLogs('reconciliation.logista_service', level='WARNING') as logs:
            self.assertFalse(notifica_n8n(job)['ok'])
        self.assertEqual(urlopen.call_count, 2)
        self.assertNotIn(TOKEN, '\n'.join(logs.output))

    def test_url_vuoto_non_fa_nulla(self):
        job = self._job(stato=LogistaInvioJob.ERRORE, errore='x')
        with patch.dict('os.environ', {'N8N_TABACCHI_WEBHOOK_URL': ''}), \
                patch('urllib.request.urlopen') as urlopen:
            self.assertFalse(notifica_n8n(job)['ok'])
        urlopen.assert_not_called()

    def test_in_corso_non_notifica(self):
        job = self._job()
        with patch('urllib.request.urlopen') as urlopen:
            self.assertFalse(notifica_n8n(job)['ok'])
        urlopen.assert_not_called()

    def test_token_ripiega_su_gratta(self):
        job = self._job(stato=LogistaInvioJob.ERRORE, errore='x')
        with patch.dict('os.environ', {'N8N_TABACCHI_TOKEN': '', 'N8N_GRATTA_TOKEN': 'token-gratta'}), \
                patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
            notifica_n8n(job)
        self.assertEqual(urlopen.call_args[0][0].get_header('X-api-key'), 'token-gratta')

    def test_esegui_job_notifica_a_fine_job(self):
        from reconciliation.logista_service import esegui_job

        job = self._job()
        risposte = [
            MagicMock(**{'read.return_value': json.dumps({'esito': 'proposta_non_vuota', 'righe_presenti': 3}).encode()}),
            _ok(),
        ]
        for risposta in risposte:
            risposta.__enter__.return_value = risposta
            risposta.__exit__.return_value = False
        with patch('urllib.request.urlopen', side_effect=risposte) as urlopen, \
                patch('reconciliation.logista_service.close_old_connections'):
            esegui_job(job.id, [{'codice': '0201', 'qta': '1,8'}])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(urlopen.call_args_list[1][0][0].full_url, WEBHOOK)
        self.assertEqual(json.loads(urlopen.call_args_list[1][0][0].data)['stato'], 'attesa_conferma')


BOT = 'bot-token-segreto'


@patch.dict('os.environ', {**ENV, 'N8N_TABACCHI_WEBHOOK_URL': '', 'TELEGRAM_BOT_TOKEN': BOT})
@patch('reconciliation.user_notifications.telegram_chat_ids_for_company', return_value=['555'])
class NotificaTelegramTests(_Base):
    def _job(self, **campi):
        return LogistaInvioJob.objects.create(
            company=self.company, preordine=self._preordine(), righe_inviate=2, **campi,
        )

    def _media(self):
        from pathlib import Path
        cartella = Path(self.media.name) / 'logista'
        cartella.mkdir(parents=True, exist_ok=True)
        return cartella

    def test_successo_con_foto(self, _chat):
        from reconciliation.logista_service import notifica_telegram

        with override_settings(MEDIA_ROOT=self.media.name):
            (self._media() / '7_invio.jpg').write_bytes(b'\xff\xd8invio')
            job = self._job(
                stato=LogistaInvioJob.INVIATO,
                codice_ordine='ORD-77',
                data_consegna_logista='23/11/2026',
                foto_invio_path='logista/7_invio.jpg',
                risultato={
                    'inserite': 1,
                    'rifiutate': [{'codice': '2423', 'qta': '0,2', 'errore': 'Fuori catalogo'}],
                    'invio': {
                        'esito': 'inviato', 'totali': ['Totale con IVA 522,00 €'],
                        'kg_tabacco': '1,800', 'pezzi_elettronici': '4', 'totale_importo': '522,00 €',
                    },
                },
            )
            with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
                self.assertEqual(notifica_telegram(job)['consegnate'], 1)
        richiesta = urlopen.call_args[0][0]
        self.assertTrue(richiesta.full_url.endswith('/sendPhoto'))
        corpo = richiesta.data.decode('utf-8', errors='replace')
        self.assertIn('✅ Ordine Logista INVIATO', corpo)
        self.assertIn('Codice ordine: ORD-77   Consegna: 23/11/2026', corpo)
        self.assertIn('Tabacco: 1,800 kg · Altri prodotti: 4 pz', corpo)
        self.assertIn('Importo: 522,00 €', corpo)
        self.assertIn('Righe inserite: 1/2', corpo)
        self.assertIn('2423 0,2 → Fuori catalogo', corpo)
        self.assertIn(b'\xff\xd8invio', richiesta.data)

    def test_fallimento_solo_testo(self, _chat):
        from reconciliation.logista_service import notifica_telegram

        job = self._job(
            stato=LogistaInvioJob.NON_INVIATO,
            fase='data',
            errore='Data di consegna non disponibile',
            risultato={'inserite': 2, 'rifiutate': []},
        )
        with override_settings(MEDIA_ROOT=self.media.name), \
                patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
            self.assertEqual(notifica_telegram(job)['consegnate'], 1)
        richiesta = urlopen.call_args[0][0]
        self.assertTrue(richiesta.full_url.endswith('/sendMessage'))
        testo = urllib.parse.parse_qs(richiesta.data.decode())['text'][0]
        self.assertEqual(testo, '\n'.join([
            '⚠️ Ordine Logista NON inviato',
            'Fase: data  Motivo: Data di consegna non disponibile',
            'La proposta caricata è rimasta su WebT: controlla e invia a mano.',
        ]))

    def test_incerto_mai_invia_a_mano(self, _chat):
        from reconciliation.logista_service import testo_telegram

        job = self._job(stato=LogistaInvioJob.INCERTO, fase='invio', errore='Esito non letto', risultato={'inserite': 2})
        testo = testo_telegram(job)
        self.assertTrue(testo.startswith(
            "❓ Esito invio non confermato. L'ordine potrebbe essere già partito: "
            'NON reinviare, controlla su WebT (Report → ordini).'
        ))
        self.assertIn('Esito non letto', testo)
        self.assertNotIn('invia a mano', testo)

    def test_token_su_altra_azienda(self, _chat):
        from reconciliation.logista_telegram import canale
        from reconciliation.models import AppSetting

        altra = Company.objects.create(denominazione='Bar')
        AppSetting.objects.create(company=altra, key='telegram_bot_token', value='tok-altra')
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': ''}):
            info = canale(self.company)
        self.assertEqual(info['token'], 'tok-altra')
        self.assertIn('Bar', info['fonte_token'])

    def test_chat_da_env(self, chat):
        from reconciliation.logista_telegram import canale

        with patch.dict('os.environ', {'TELEGRAM_LOGISTA_CHAT_IDS': '11, 22'}):
            self.assertEqual(canale(self.company)['chat_ids'], ['11', '22'])
        chat.assert_not_called()

    def test_senza_token_o_chat_motivo_chiaro(self, chat):
        from reconciliation.logista_telegram import notifica

        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': ''}), \
                self.assertLogs('reconciliation.logista_telegram', level='WARNING'):
            self.assertIn('Token bot Telegram assente', notifica(self.company, 'x')['motivo'])
        chat.return_value = []
        with self.assertLogs('reconciliation.logista_telegram', level='WARNING'):
            self.assertIn('Nessuna chat Telegram', notifica(self.company, 'x')['motivo'])

    def test_esito_salvato_nel_job_con_codice_http(self, _chat):
        from reconciliation.logista_service import esegui_job

        job = self._job(stato=LogistaInvioJob.IN_CORSO_CARICAMENTO)
        rifiuto = urllib.error.HTTPError(
            'https://api.telegram.org/x', 403, 'Forbidden', {},
            io.BytesIO(b'{"ok":false,"description":"Forbidden: bot was blocked by the user"}'),
        )
        with override_settings(MEDIA_ROOT=self.media.name), patch.dict('os.environ', {
            'LOGISTA_SERVICE_KEY': 'chiave-logista',
        }), patch('urllib.request.urlopen', side_effect=[
            _json_ok({'esito': 'caricato', 'inserite': 0}), rifiuto,
        ]), patch('reconciliation.logista_service.close_old_connections'), \
                self.assertLogs('reconciliation.logista_telegram', level='WARNING') as logs:
            esegui_job(job.id, [{'codice': '0201', 'qta': '1,8'}])
        job.refresh_from_db()
        self.assertEqual(job.stato, LogistaInvioJob.NON_INVIATO)
        tentativo = job.notifica_esito['telegram']['tentativi'][0]
        self.assertEqual(tentativo['http'], 403)
        self.assertIn('bot was blocked', tentativo['dettaglio'])
        self.assertIn('HTTP 403', '\n'.join(logs.output))
        self.assertNotIn(BOT, json.dumps(job.notifica_esito))

    def test_comando_prova(self, _chat):
        from django.core.management import call_command

        uscita = io.StringIO()
        with patch('urllib.request.urlopen', return_value=_ok()) as urlopen:
            call_command('prova_notifica_logista', '--company', str(self.company.id), stdout=uscita)
        testo = urllib.parse.parse_qs(urlopen.call_args[0][0].data.decode())['text'][0]
        self.assertEqual(testo, '🧪 Test notifica ordine Logista')
        self.assertIn('OK HTTP 200', uscita.getvalue())
        self.assertNotIn(BOT, uscita.getvalue())

    def test_comando_prova_fallita(self, chat):
        from django.core.management import CommandError, call_command

        chat.return_value = []
        with self.assertRaises(CommandError), self.assertLogs('reconciliation.logista_telegram', level='WARNING'):
            call_command('prova_notifica_logista', '--company', str(self.company.id), stdout=io.StringIO())

    def test_errore_rete_solo_log_senza_token(self, _chat):
        from reconciliation.logista_service import notifica_telegram

        job = self._job(stato=LogistaInvioJob.ERRORE, fase='caricamento', errore='giù')
        with override_settings(MEDIA_ROOT=self.media.name), \
                patch('urllib.request.urlopen', side_effect=urllib.error.URLError('down')), \
                self.assertLogs('reconciliation.logista_telegram', level='WARNING') as logs:
            self.assertFalse(notifica_telegram(job)['ok'])
        self.assertNotIn(BOT, '\n'.join(logs.output))
        self.assertIn('URLError', '\n'.join(logs.output))


@patch.dict('os.environ', ENV)
class AvviaN8nTests(_Base):
    URL = '/api/n8n/tabacchi/logista/avvia/'

    def _post(self, token=TOKEN, body=None):
        headers = {'HTTP_X_N8N_TOKEN': token} if token is not None else {}
        return self.client.post(
            self.URL, data=json.dumps(body or {'svuota': False}), content_type='application/json', **headers,
        )

    def test_auth(self):
        self._agente()
        self.assertEqual(self._post(token=None).status_code, 401)
        self.assertEqual(self._post(token='sbagliato').status_code, 401)
        self.assertEqual(self.client.get('/api/n8n/tabacchi/logista/job/1/').status_code, 401)
        with patch.dict('os.environ', {'N8N_TABACCHI_TOKEN': '', 'N8N_GRATTA_TOKEN': ''}):
            self.assertEqual(self._post(token='').status_code, 401)

    def test_409_job_in_corso(self):
        self._agente()
        attivo = LogistaInvioJob.objects.create(company=self.company, preordine=self._preordine())
        response = self._post()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['job_id'], attivo.id)

    def test_503_agente_offline(self):
        self._agente(online=False)
        response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['errore'], 'Agente TabaUno non raggiungibile')
        self.assertFalse(TabaUnoRequest.objects.exists())

    def test_503_agente_non_risponde_entro_timeout(self):
        self._agente()
        with patch('reconciliation.n8n_tabacchi_views.LETTURA_TIMEOUT', 0), \
                patch('reconciliation.n8n_tabacchi_views.time.sleep'):
            response = self._post()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['errore'], 'Agente TabaUno non raggiungibile')
        self.assertFalse(LogistaInvioJob.objects.exists())

    def test_avvia_crea_preordine_nuovo_e_job_telegram(self):
        self._agente()

        def agente_risponde(_secondi):
            TabaUnoRequest.objects.filter(status=TabaUnoRequest.PENDING).update(
                status=TabaUnoRequest.DONE, payload=_lettura_payload(),
            )

        with patch('reconciliation.n8n_tabacchi_views.time.sleep', side_effect=agente_risponde), \
                patch('reconciliation.logista_service.avvia_job') as avvia:
            response = self._post(body={'svuota': True})
        self.assertEqual(response.status_code, 202, response.content)
        data = response.json()
        job = LogistaInvioJob.objects.get(id=data['job_id'])
        self.assertEqual(job.origine, LogistaInvioJob.ORIGINE_TELEGRAM)
        self.assertTrue(job.svuota)
        self.assertEqual(data['righe'], job.righe_inviate)
        self.assertGreater(data['righe'], 0)
        preordine = TabacchiPreordine.objects.get(id=data['preordine_id'])
        self.assertEqual(preordine.giorni_copertura, 7)
        self.assertEqual(data['kg_tabacco'], float(preordine.kg))
        self.assertEqual(data['valore_stimato'], float(preordine.totale))
        _job, righe = avvia.call_args[0]
        self.assertEqual(righe[0]['codice'], '0201')

        stato = self.client.get(f'/api/n8n/tabacchi/logista/job/{job.id}/', HTTP_X_N8N_TOKEN=TOKEN)
        self.assertEqual(stato.status_code, 200)
        self.assertEqual(stato.json()['job']['origine'], 'telegram')
        self.assertNotIn('chiave-logista', stato.content.decode())
