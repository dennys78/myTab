import hashlib
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.incassi_parziali import (
    formatta_euro,
    normalizza_payload,
    testo_telegram,
)
from reconciliation.models import Company, TabaUnoAgent

TOKEN = 'token-n8n-incassi'
ENV = {
    'N8N_TABACCHI_TOKEN': TOKEN,
    'N8N_GRATTA_TOKEN': '',
}


def _payload_base(**overrides):
    data = {
        'data': '2026-11-21',
        'ultima_ora': '11:05',
        'righe_totali': 8,
        'letto_alle': '2026-11-21T11:10:00',
        'settori': [
            {'codice': '01', 'descrizione': 'TABACCHI', 'n': 3, 'importo': 1579.9},
            {'codice': '90', 'descrizione': 'GRATTA', 'n': 2, 'importo': 465.0},
            {'codice': '301', 'descrizione': 'INCASSO LOTTO/10&LOTTO', 'n': 4, 'importo': 409.5},
            {'codice': '300', 'descrizione': 'VINCITE', 'n': 1, 'importo': 999.0},
            {'codice': '02', 'descrizione': 'CAFFE', 'n': 1, 'importo': 54.6},
            {'codice': '09', 'descrizione': 'ROSTICCERIA', 'n': 1, 'importo': 16.0},
            {'codice': '03', 'descrizione': 'PASTICCERIA', 'n': 1, 'importo': 8.1},
            {'codice': '97', 'descrizione': 'ALTRO', 'n': 1, 'importo': 50.0},
        ],
    }
    data.update(overrides)
    return data


class NormalizzaParzialiTests(TestCase):
    def test_solo_settori_configurati_gratta_senza_300(self):
        dati = normalizza_payload(_payload_base(), oggi=date(2026, 11, 21))
        self.assertEqual(set(dati['settori']), {'tabacchi', 'gratta', 'caffe', 'rosticceria', 'pasticceria'})
        self.assertEqual(dati['settori']['gratta']['importo'], 465.0)
        self.assertEqual(dati['settori']['tabacchi']['importo'], 1579.9)
        self.assertNotIn('lottomatica', dati['settori'])
        self.assertAlmostEqual(dati['totale'], 1579.9 + 465 + 54.6 + 16 + 8.1)
        self.assertFalse(dati['cassa_non_oggi'])
        self.assertFalse(dati['nessuna_vendita'])

    def test_giornata_vuota(self):
        dati = normalizza_payload({
            'data': '', 'ultima_ora': '', 'righe_totali': 0, 'settori': [], 'letto_alle': '',
        }, oggi=date(2026, 11, 21))
        self.assertTrue(dati['nessuna_vendita'])
        self.assertEqual(dati['totale'], 0.0)
        testo = testo_telegram(dati)
        self.assertIn('Nessuna vendita registrata dalla chiusura precedente.', testo)

    def test_data_diversa_da_oggi(self):
        dati = normalizza_payload(_payload_base(data='2026-11-20'), oggi=date(2026, 11, 21))
        self.assertTrue(dati['cassa_non_oggi'])
        testo = testo_telegram(dati)
        self.assertIn('cassa del 20/11 non ancora chiusa', testo)

    def test_formattazione_telegram(self):
        self.assertEqual(formatta_euro(1579.9), '1.579,90 €')
        dati = normalizza_payload(_payload_base(), oggi=date(2026, 11, 21))
        testo = testo_telegram(dati)
        self.assertIn('💶 <b>Incassi di oggi – sab 21/11</b>', testo)
        self.assertIn('(ultima vendita 11:05)', testo)
        self.assertIn('🚬 Tabacchi: <b>1.579,90 €</b>', testo)
        self.assertIn('🎟️ Gratta e Vinci: <b>465,00 €</b>', testo)
        self.assertNotIn('Lottomatica', testo)
        self.assertIn('Totale settori: <b>2.123,60 €</b>', testo)
        self.assertNotIn('999', testo)


@patch.dict('os.environ', ENV)
class ApiN8nIncassiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Incassi')
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'agent').hexdigest(),
            last_seen=timezone.now(),
        )

    def _post(self, token=TOKEN, body=None):
        return self.client.post(
            '/api/n8n/cassa/parziali/',
            data=json.dumps(body if body is not None else {'company_id': self.company.id}),
            content_type='application/json',
            HTTP_X_N8N_TOKEN=token,
        )

    def test_auth_401(self):
        r = self._post(token='sbagliato')
        self.assertEqual(r.status_code, 401)

    @patch('reconciliation.incassi_parziali.agent_is_online', return_value=False)
    def test_offline_503(self, _online):
        r = self._post()
        self.assertEqual(r.status_code, 503)
        data = r.json()
        self.assertEqual(data['errore'], 'PC negozio offline')
        self.assertIn('Incassi non disponibili', data['messaggi'][0])

    @patch('reconciliation.incassi_parziali.agent_is_online', return_value=True)
    @patch('reconciliation.incassi_parziali.attendi_lettura', return_value=None)
    @patch('reconciliation.incassi_parziali.accoda_parziali')
    def test_lettura_fallita_503(self, mock_accoda, _attendi, _online):
        from reconciliation.models import TabaUnoRequest
        mock_accoda.return_value = (TabaUnoRequest(company=self.company), True)
        r = self._post()
        self.assertEqual(r.status_code, 503)
        self.assertIn('Lettura', r.json()['errore'])

    @patch('reconciliation.incassi_parziali.agent_is_online', return_value=True)
    @patch('reconciliation.incassi_parziali.attendi_lettura')
    @patch('reconciliation.incassi_parziali.accoda_parziali')
    def test_ok_200(self, mock_accoda, mock_attendi, _online):
        from reconciliation.models import TabaUnoRequest
        row = TabaUnoRequest.objects.create(
            company=self.company,
            date=date(2026, 11, 21),
            tipo=TabaUnoRequest.TIPO_PARZIALI_CASSA,
            status=TabaUnoRequest.DONE,
            payload=_payload_base(),
        )
        mock_accoda.return_value = (row, True)
        mock_attendi.return_value = row
        with patch('reconciliation.incassi_parziali.timezone.localdate', return_value=date(2026, 11, 21)):
            r = self._post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('messaggi', data)
        self.assertIn('testo', data)
        self.assertEqual(data['settori']['gratta']['importo'], 465.0)
        self.assertNotIn('300', str(data['settori']))


class ApiIncassiDashboardTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria UI')
        self.user = User.objects.create_user('op-inc', password='secret', is_staff=True)
        self.client.login(username='op-inc', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'a').hexdigest(),
            last_seen=timezone.now(),
        )

    @patch('reconciliation.incassi_views.agent_is_online', return_value=False)
    def test_offline_409(self, _online):
        r = self.client.post('/api/incassi/parziali/', data='{}', content_type='application/json')
        self.assertEqual(r.status_code, 409)
