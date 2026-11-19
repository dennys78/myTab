import base64
import io
import json
import tempfile
import urllib.error
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from reconciliation.logista_service import (
    LogistaServiceError,
    esegui_job,
    posta_carica,
    righe_logista_payload,
)
from reconciliation.models import (
    Company,
    LogistaInvioJob,
    TabacchiPreordine,
    TabacchiPreordineRiga,
    TabaUnoRequest,
)

ENV = {
    'LOGISTA_SERVICE_URL': 'http://logista.test:3501',
    'LOGISTA_SERVICE_KEY': 'chiave-segreta',
    'N8N_TABACCHI_WEBHOOK_URL': '',
    'TELEGRAM_BOT_TOKEN': '',
}
CARICATO = {
    'esito': 'caricato',
    'inserite': 1,
    'rifiutate': [{'codice': '2423', 'qta': '0,2', 'errore': 'Codice non ordinabile'}],
    'avvisi': [{'codice': '0201', 'avvisi': ['Quantità arrotondata']}],
    'proposta': {'tabacchi': 1, 'altri': 0, 'testo': 'Proposta 1 riga'},
}


def _risposta(data):
    response = MagicMock()
    response.read.return_value = json.dumps(data).encode('utf-8')
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


def _http_error(code, data):
    return urllib.error.HTTPError(
        'http://logista.test:3501/logista/carica', code, 'err', {}, io.BytesIO(json.dumps(data).encode()),
    )


class RigheLogistaTests(TestCase):
    def test_zeri_iniziali_virgola_e_zero_esclusi(self):
        righe = [
            {'aams': '201', 'unita': 9, 'kg_per_unita': Decimal('0.200'), 'famiglia': 'Sigarette'},
            {'aams': '20659', 'unita': 0, 'kg_per_unita': Decimal('0.200'), 'famiglia': 'Sigarette'},
            {'aams': '33', 'unita': 2, 'kg_per_unita': Decimal('0.025'), 'famiglia': 'Trinciati'},
            {'aams': 'T5000', 'unita': 3, 'kg_per_unita': 0, 'famiglia': 'Dispositivi'},
        ]
        self.assertEqual(righe_logista_payload(righe), [
            {'codice': '0201', 'qta': '1,8'},
            {'codice': '0033', 'qta': '0,05'},
            {'codice': 'T5000', 'qta': '3'},
        ])


@patch.dict('os.environ', ENV)
class PostaCaricaTests(TestCase):
    def test_invia_chiave_e_corpo(self):
        with patch('urllib.request.urlopen', return_value=_risposta({'esito': 'caricato'})) as urlopen:
            posta_carica('http://logista.test:3501', 'chiave-segreta', [{'codice': '0201', 'qta': '1,8'}], True)
        richiesta = urlopen.call_args[0][0]
        self.assertEqual(richiesta.full_url, 'http://logista.test:3501/logista/carica')
        self.assertEqual(richiesta.get_header('X-api-key'), 'chiave-segreta')
        self.assertEqual(
            json.loads(richiesta.data),
            {'righe': [{'codice': '0201', 'qta': '1,8'}], 'svuota': True},
        )

    def test_errori_leggibili_senza_chiave(self):
        casi = [
            (_http_error(409, {'errore': 'occupato'}), 'occupato'),
            (_http_error(500, {'errore': 'login fallito'}), 'login fallito'),
            (urllib.error.URLError('refused'), 'non raggiungibile'),
        ]
        for errore, atteso in casi:
            with patch('urllib.request.urlopen', side_effect=errore):
                with self.assertRaises(LogistaServiceError) as ctx:
                    posta_carica('http://logista.test:3501', 'chiave-segreta', [], False)
            self.assertIn(atteso, str(ctx.exception))
            self.assertNotIn('chiave-segreta', str(ctx.exception))


@patch.dict('os.environ', ENV)
class LogistaApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Logista')
        self.user = User.objects.create_user('op-log', password='secret', is_staff=True)
        self.client.login(username='op-log', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()
        lettura = TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
            status=TabaUnoRequest.DONE,
            requested_by=self.user,
        )
        self.preordine = TabacchiPreordine.objects.create(
            company=self.company,
            creato_da=self.user,
            request=lettura,
            data_consegna=timezone.localdate() + timedelta(days=5),
        )
        TabacchiPreordineRiga.objects.create(
            preordine=self.preordine, aams='201', unita=9, kg_per_unita=Decimal('0.200'), famiglia='Sigarette',
        )
        TabacchiPreordineRiga.objects.create(
            preordine=self.preordine, aams='2423', unita=0, kg_per_unita=Decimal('0.200'), famiglia='Sigarette',
        )
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)

    def _invia(self, svuota=False):
        with patch('reconciliation.logista_service.avvia_job') as avvia:
            response = self.client.post(
                '/api/tabacchi/logista/invia/',
                data=json.dumps({'preordine_id': self.preordine.id, 'svuota': svuota}),
                content_type='application/json',
            )
        return response, avvia

    def _job(self, job_id):
        return self.client.get(f'/api/tabacchi/logista/job/{job_id}/').json()['job']

    def test_non_configurato(self):
        with patch.dict('os.environ', {'LOGISTA_SERVICE_KEY': ''}):
            response, avvia = self._invia()
        self.assertEqual(response.status_code, 503)
        self.assertIn('non configurato', response.json()['error'])
        avvia.assert_not_called()

    def test_invia_righe_e_blocca_secondo_job(self):
        response, avvia = self._invia()
        self.assertEqual(response.status_code, 202)
        job, righe = avvia.call_args[0]
        self.assertEqual(righe, [{'codice': '0201', 'qta': '1,8'}])
        self.assertEqual(job.righe_inviate, 1)
        self.assertEqual(response.json()['job_id'], job.id)
        doppio, _ = self._invia()
        self.assertEqual(doppio.status_code, 409)
        self.assertEqual(doppio.json()['job_id'], job.id)

    def test_job_orfano_scade(self):
        response, _ = self._invia()
        job_id = response.json()['job_id']
        LogistaInvioJob.objects.filter(id=job_id).update(creato_il=timezone.now() - timedelta(minutes=31))
        with patch('reconciliation.logista_service.threading.Thread') as thread:
            self.assertEqual(self._job(job_id)['stato'], LogistaInvioJob.ERRORE)
        self.assertEqual(thread.call_args[1]['args'], (job_id,))
        nuovo, _ = self._invia()
        self.assertEqual(nuovo.status_code, 202)

    def test_proposta_non_vuota(self):
        response, _ = self._invia()
        job_id = response.json()['job_id']
        with patch('urllib.request.urlopen', return_value=_risposta({
            'esito': 'proposta_non_vuota', 'righe_presenti': 12,
        })):
            esegui_job(job_id, [{'codice': '0201', 'qta': '1,8'}])
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.ATTESA_CONFERMA)
        self.assertEqual(job['righe_presenti'], 12)

    def _esegui(self, *risposte):
        response, _ = self._invia()
        job_id = response.json()['job_id']
        with override_settings(MEDIA_ROOT=self.media.name), \
                patch('urllib.request.urlopen', side_effect=list(risposte)) as urlopen:
            esegui_job(job_id, [{'codice': '0201', 'qta': '1,8'}])
        return job_id, urlopen

    def test_caricato_e_inviato(self):
        foto = b'\xff\xd8\xff\xe0carica'
        foto_invio = b'\xff\xd8\xff\xe0invio'
        job_id, urlopen = self._esegui(_risposta(CARICATO | {
            'foto_jpeg_base64': base64.b64encode(foto).decode(),
        }), _risposta({
            'esito': 'inviato',
            'codice_ordine': 'ORD-123',
            'data_consegna': '23/11/2026',
            'conferma': 'Ordine inviato',
            'totali': ['Totale con IVA: 522,00 €'],
            'kg_tabacco': '1,800',
            'pezzi_elettronici': '4',
            'totale_importo': '522,00 €',
            'passi': ['riepilogo', 'invio'],
            'foto_jpeg_base64': base64.b64encode(foto_invio).decode(),
        }))
        self.assertEqual(urlopen.call_count, 2)
        invio = urlopen.call_args_list[1][0][0]
        self.assertEqual(invio.full_url, 'http://logista.test:3501/logista/invia')
        self.assertEqual(json.loads(invio.data), {'conferma': True})
        self.assertEqual(urlopen.call_args_list[1][1]['timeout'], 300)
        with override_settings(MEDIA_ROOT=self.media.name):
            job = self._job(job_id)
            self.assertEqual(b''.join(self.client.get(job['foto_url']).streaming_content), foto)
            self.assertEqual(b''.join(self.client.get(job['foto_invio_url']).streaming_content), foto_invio)
        self.assertEqual(job['stato'], LogistaInvioJob.INVIATO)
        self.assertEqual(job['codice_ordine'], 'ORD-123')
        self.assertEqual(job['data_consegna'], '23/11/2026')
        self.assertEqual(job['totali'], ['Totale con IVA: 522,00 €'])
        self.assertEqual(job['totale_importo'], '522,00 €')
        self.assertEqual(job['kg_tabacco'], '1,800')
        self.assertEqual(job['pezzi_elettronici'], '4')
        self.assertEqual(job['avviso_incerto'], '')
        self.assertEqual(job['inserite'], 1)
        self.assertEqual(job['rifiutate'][0]['errore'], 'Codice non ordinabile')
        salvato = LogistaInvioJob.objects.get(id=job_id)
        self.assertNotIn('foto_jpeg_base64', salvato.risultato)
        self.assertNotIn('foto_jpeg_base64', salvato.risultato['invio'])
        self.assertEqual(salvato.foto_invio_path, f'logista/{job_id}_invio.jpg')

    def test_bloccato_non_inviato(self):
        job_id, urlopen = self._esegui(_risposta(CARICATO), _risposta({
            'esito': 'bloccato', 'fase': 'data', 'messaggio': 'Data di consegna non disponibile',
            'passi': [], 'foto_jpeg_base64': base64.b64encode(b'blocco').decode(),
        }))
        self.assertEqual(urlopen.call_count, 2)
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.NON_INVIATO)
        self.assertEqual(job['fase'], 'data')
        self.assertEqual(job['errore'], 'Data di consegna non disponibile')
        self.assertTrue(job['foto_invio_url'])

    def test_incerto_nessun_retry(self):
        job_id, urlopen = self._esegui(_risposta(CARICATO), _risposta({
            'esito': 'incerto', 'messaggio': 'Pagina di conferma non trovata',
        }))
        self.assertEqual(urlopen.call_count, 2)
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.INCERTO)
        self.assertEqual(job['errore'], 'Pagina di conferma non trovata')
        self.assertIn('NON reinviare', job['avviso_incerto'])

    def test_errore_http_invio_nessun_retry(self):
        job_id, urlopen = self._esegui(
            _risposta(CARICATO), _http_error(500, {'errore': 'Sessione scaduta'}),
        )
        self.assertEqual(urlopen.call_count, 2)
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.INCERTO)
        self.assertEqual(job['fase'], 'invio')
        self.assertIn('Sessione scaduta', job['errore'])

    def test_timeout_invio_esito_incerto(self):
        job_id, urlopen = self._esegui(_risposta(CARICATO), urllib.error.URLError(TimeoutError('timed out')))
        self.assertEqual(urlopen.call_count, 2)
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.INCERTO)
        self.assertIn('tempo scaduto', job['errore'])

    def test_occupato_su_invio_non_inviato_certo(self):
        job_id, _ = self._esegui(_risposta(CARICATO), _http_error(409, {'errore': 'occupato'}))
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.NON_INVIATO)
        self.assertIn('occupato', job['errore'])

    def test_inserite_zero_non_invia(self):
        job_id, urlopen = self._esegui(_risposta(CARICATO | {'inserite': 0}))
        self.assertEqual(urlopen.call_count, 1)
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.NON_INVIATO)
        self.assertIn('Nessuna riga accettata', job['errore'])

    def test_errore_servizio(self):
        response, _ = self._invia()
        job_id = response.json()['job_id']
        with patch('urllib.request.urlopen', side_effect=_http_error(502, {'errore': 'WebT non risponde'})):
            esegui_job(job_id, [{'codice': '0201', 'qta': '1,8'}])
        job = self._job(job_id)
        self.assertEqual(job['stato'], LogistaInvioJob.ERRORE)
        self.assertIn('WebT non risponde', job['errore'])
        self.assertNotIn('chiave-segreta', json.dumps(job))
