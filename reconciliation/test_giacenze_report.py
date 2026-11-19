import hashlib
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from reconciliation.giacenze_report import (
    corpo_da_lettura,
    costruisci_testo,
    escape_html,
    formatta_data_corta,
    messaggio_indisponibile,
    sezioni_report,
    spezza_messaggi,
)
from reconciliation.giacenze_stats import ESAURITO, FERMO, OK, PRIMA_CONSEGNA, RISCHIO
from reconciliation.models import Company, TabaUnoAgent, TabaUnoRequest

TOKEN = 'token-n8n-giacenze'
ENV = {
    'N8N_TABACCHI_TOKEN': TOKEN,
    'N8N_GRATTA_TOKEN': '',
}


def _righe_esempio():
    return [
        {
            'aams': '1', 'descrizione': 'MARLBORO GOLD', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 0, 'media': 3.2, 'stato': ESAURITO, 'immancabile': True,
            'giorni_fine': 0, 'data_fine': None, 'mancanti_alla_data': 13,
        },
        {
            'aams': '2', 'descrizione': 'CAMEL BLUE', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 4, 'media': 1.8, 'stato': PRIMA_CONSEGNA, 'immancabile': True,
            'giorni_fine': 2, 'data_fine': '2026-11-21', 'mancanti_alla_data': 3,
        },
        {
            'aams': '3', 'descrizione': 'LENTO', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 2, 'media': 0.6, 'stato': RISCHIO, 'immancabile': False,
            'giorni_fine': 3, 'data_fine': '2026-11-22', 'mancanti_alla_data': 1,
        },
        {
            'aams': '4', 'descrizione': 'OKAY', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 50, 'media': 2, 'stato': OK, 'immancabile': False,
            'giorni_fine': 20, 'data_fine': '2026-12-10', 'mancanti_alla_data': 0,
        },
        {
            'aams': '5', 'descrizione': 'FERMO', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 10, 'media': 0, 'stato': FERMO, 'immancabile': False,
            'giorni_fine': None, 'data_fine': None, 'mancanti_alla_data': 0,
        },
        {
            'aams': '6', 'descrizione': 'DEBole', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 1, 'media': 0.4, 'stato': PRIMA_CONSEGNA, 'immancabile': False,
            'giorni_fine': 1, 'data_fine': '2026-11-20', 'mancanti_alla_data': 2,
        },
    ]


class SezioniReportTests(TestCase):
    def test_immancabili_e_prima_di_lunedi(self):
        imm, prima = sezioni_report({'righe': _righe_esempio()})
        self.assertEqual([r['aams'] for r in imm], ['1', '2'])  # esaurito prima di prima_consegna
        self.assertEqual([r['aams'] for r in prima], ['6', '3'])  # per data_fine; media 0 esclusa; OK escluso
        self.assertTrue(all(r['media'] > 0 for r in imm + prima))


class FormattazioneReportTests(TestCase):
    def test_data_corta_e_escape(self):
        # 2026-11-19 = giovedì, 2026-11-20 = venerdì
        self.assertEqual(formatta_data_corta(date(2026, 11, 19)), 'gio 19/11')
        self.assertEqual(formatta_data_corta(date(2026, 11, 20)), 'ven 20/11')
        self.assertEqual(escape_html('A <B> & C'), 'A &lt;B&gt; &amp; C')

    def test_testo_sezioni_e_vuoto(self):
        oggi = date(2026, 11, 19)  # gio
        lunedi = date(2026, 11, 24)
        consegna = date(2026, 11, 24)
        imm, prima = sezioni_report({'righe': _righe_esempio()})
        testo = costruisci_testo(
            oggi=oggi, lunedi=lunedi, consegna=consegna,
            ultimo_giorno_chiuso='2026-11-18',
            letto_alle='2026-11-19T10:05:00',
            immancabili=imm, prima_di_lunedi=prima,
        )
        self.assertIn('📦 <b>Giacenze – gio 19/11</b>', testo)
        self.assertIn('dati chiusura 18/11', testo)
        self.assertIn('letti alle 10:05', testo)
        self.assertIn('🔴 <b>IMMANCABILI (2)</b>', testo)
        self.assertIn('<b>ESAURITO</b>', testo)
        self.assertIn('🟠 <b>FINISCONO PRIMA DI LUNEDÌ 24/11 (2)</b>', testo)
        self.assertIn('3,2/gg', testo)
        self.assertNotIn('FERMO', testo)

        vuoto = costruisci_testo(
            oggi=oggi, lunedi=lunedi, consegna=consegna,
            ultimo_giorno_chiuso='2026-11-18', letto_alle='',
            immancabili=[], prima_di_lunedi=[],
        )
        self.assertIn('✅ Nessun articolo in esaurimento fino a lunedì', vuoto)

    def test_spezza_senza_tagliare_righe(self):
        linee = [f'riga-{i}-{"x" * 80}' for i in range(60)]
        testo = '\n'.join(linee)
        pezzi = spezza_messaggi(testo, max_len=400)
        self.assertGreater(len(pezzi), 1)
        self.assertEqual('\n'.join(pezzi), testo)
        for pezzo in pezzi:
            self.assertLessEqual(len(pezzo), 400)
            for linea in pezzo.split('\n'):
                self.assertTrue(linea.startswith('riga-') or linea == '')

    def test_messaggio_indisponibile(self):
        pezzi = messaggio_indisponibile('PC negozio offline')
        self.assertEqual(len(pezzi), 1)
        self.assertIn('Report giacenze non disponibile', pezzi[0])
        self.assertIn('PC negozio offline', pezzi[0])


class CorpoDaLetturaTests(TestCase):
    def test_payload_reale_sezioni(self):
        ultimo = date(2026, 11, 19)
        aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 28)]
        payload = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': aperture,
            'letto_alle': '2026-11-20T09:30:00+01:00',
            'articoli': [
                {
                    'aams': 'E1', 'descrizione': 'ESAURITO HOT', 'categoria': 'SIGARETTE',
                    'prezzo': 5.8, 'prezzo_kg': 290, 'minimo_grammi': 200,
                    'giacenza': 0,
                    'vendite_giornaliere': {day: 5 for day in aperture},
                    'giacenze_fine_giorno': {},
                },
                {
                    'aams': 'F0', 'descrizione': 'SENZA VENDITE', 'categoria': 'SIGARETTE',
                    'prezzo': 5, 'prezzo_kg': 250, 'minimo_grammi': 200,
                    'giacenza': 3,
                    'vendite_giornaliere': {},
                    'giacenze_fine_giorno': {},
                },
            ],
        }
        body = corpo_da_lettura(payload, oggi=date(2026, 11, 20), giorno_consegna=0)
        self.assertEqual(body['data'], '2026-11-20')
        self.assertEqual(body['lunedi'], '2026-11-23')  # prossimo lunedì dopo ven 20/11
        self.assertTrue(any(r['aams'] == 'E1' for r in body['immancabili']))
        self.assertFalse(any(r['aams'] == 'F0' for r in body['immancabili'] + body['prima_di_lunedi']))
        self.assertIn('messaggi', body)
        self.assertEqual(body['messaggi'][0], body['testo'])
        self.assertTrue(body['messaggi'])


@patch.dict('os.environ', ENV)
class ApiN8nGiacenzeReportTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Report')
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'agent').hexdigest(),
            last_seen=timezone.now(),
        )

    def _post(self, token=TOKEN, body=None):
        return self.client.post(
            '/api/n8n/giacenze/report/',
            data=json.dumps(body if body is not None else {}),
            content_type='application/json',
            HTTP_X_N8N_TOKEN=token,
        )

    def test_auth_401(self):
        r = self._post(token='sbagliato')
        self.assertEqual(r.status_code, 401)

    @patch('reconciliation.giacenze_report.agent_is_online', return_value=False)
    def test_offline_503(self, _online):
        r = self._post()
        self.assertEqual(r.status_code, 503)
        data = r.json()
        self.assertEqual(data['errore'], 'PC negozio offline')
        self.assertIn('messaggi', data)
        self.assertIn('PC negozio offline', data['messaggi'][0])
        self.assertNotIn('invia_telegram', data)
        self.assertNotIn('telegram', data)

    @patch('reconciliation.giacenze_report.agent_is_online', return_value=True)
    @patch('reconciliation.n8n_giacenze_views._attendi_lettura', return_value=None)
    @patch('reconciliation.giacenze_report.accoda_lettura')
    def test_lettura_fallita_503(self, mock_accoda, _attendi, _online):
        mock_accoda.return_value = (TabaUnoRequest(company=self.company), True)
        r = self._post(body={'company_id': self.company.id})
        self.assertEqual(r.status_code, 503)
        self.assertIn('Lettura', r.json()['errore'])

    @patch('reconciliation.giacenze_report.agent_is_online', return_value=True)
    @patch('reconciliation.n8n_giacenze_views._attendi_lettura')
    @patch('reconciliation.giacenze_report.accoda_lettura')
    def test_ok_200_senza_telegram(self, mock_accoda, mock_attendi, _online):
        ultimo = date(2026, 11, 19)
        aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 14)]
        payload = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': aperture,
            'letto_alle': '2026-11-20T10:00:00+01:00',
            'articoli': [{
                'aams': '201', 'descrizione': 'CHESTERFIELD <GOLD>', 'categoria': 'SIGARETTE',
                'prezzo': 5.8, 'prezzo_kg': 290, 'minimo_grammi': 200,
                'giacenza': 0,
                'vendite_giornaliere': {day: 4 for day in aperture},
                'giacenze_fine_giorno': {},
            }],
        }
        row = TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
            status=TabaUnoRequest.DONE,
            payload=payload,
        )
        mock_accoda.return_value = (row, True)
        mock_attendi.return_value = row
        with patch('reconciliation.giacenze_report.timezone.localdate', return_value=date(2026, 11, 20)):
            r = self._post(body={'company_id': self.company.id})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('messaggi', data)
        self.assertIn('testo', data)
        self.assertIn('immancabili', data)
        self.assertNotIn('telegram', data)
        self.assertIn('CHESTERFIELD &lt;GOLD&gt;', data['testo'])
