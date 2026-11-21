import hashlib
import json
from datetime import date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.models import Company, PortaleGiornata, TabaUnoAgent, TabaUnoRequest
from reconciliation.portale_giornata import (
    leggi_portale,
    riconcilia,
    testo_telegram,
)
from reconciliation.portale_service import PortaleServiceError

TOKEN = 'token-n8n-portale'
ENV = {
    'N8N_TABACCHI_TOKEN': TOKEN,
    'N8N_GRATTA_TOKEN': '',
    'LOGISTA_SERVICE_KEY': 'chiave-portale',
    'PORTALE_SERVICE_URL': 'http://portale.test:3500',
}

CONTABILE = {
    'data': '2026-11-21',
    'richiesto_alle': '2026-11-21T13:48:09',
    'giochi': {
        'lotto': {'giocate': 86.0, 'annullate': 0, 'vincite': 0, 'rimborsi': 0, 'n_giocate': 62},
        'diecielotto': {'giocate': 314.5, 'annullate': 0, 'vincite': 127.5, 'n_giocate': 150},
        'millionday': {'giocate': 9.0, 'annullate': 0, 'vincite': 0, 'n_giocate': 7},
        'fai3fai4': {'giocate': 0, 'annullate': 0, 'vincite': 0, 'n_giocate': 0},
    },
    'entrate': 409.5,
    'uscite': 127.5,
    'aggio': 32.76,
    'saldo': 249.24,
    'righe': [],
}

PREMI = {
    'data': '2026-11-21',
    'richiesto_alle': '2026-11-21T13:57:59',
    'giochi': [{'codice': '3058', 'qta': 1, 'importo': 10.0}],
    'totale': {'qta': 10, 'importo': 86.0},
    'righe': [],
}


class RiconciliazioneTests(TestCase):
    def test_ok_e_differenza(self):
        voci = [
            {'reparto': '301', 'descrizione': 'INCASSO LOTTO/10&LOTTO', 'entrate': 409.5, 'uscite': 0},
            {'reparto': '300', 'descrizione': 'VINCITE GRATTA E VINCI', 'entrate': 0, 'uscite': 86.0},
        ]
        ric = riconcilia(CONTABILE, PREMI, voci)
        self.assertEqual(ric['lotto_entrate']['stato'], 'ok')
        self.assertEqual(ric['gratta_premi']['stato'], 'ok')
        self.assertEqual(ric['lotto_entrate']['differenza'], 0.0)

        voci2 = [
            {'reparto': '301', 'descrizione': 'INCASSO LOTTO/10&LOTTO', 'entrate': 400.0, 'uscite': 0},
            {'reparto': '300', 'descrizione': 'VINCITE GRATTA E VINCI', 'entrate': 0, 'uscite': 80.0},
        ]
        ric2 = riconcilia(CONTABILE, PREMI, voci2)
        self.assertEqual(ric2['lotto_entrate']['stato'], 'differenza')
        self.assertAlmostEqual(ric2['lotto_entrate']['differenza'], 9.5)
        self.assertEqual(ric2['gratta_premi']['stato'], 'differenza')

    def test_testo_telegram(self):
        company = Company.objects.create(denominazione='X')
        row = PortaleGiornata.objects.create(
            company=company,
            data=date(2026, 11, 21),
            contabile_lotto=CONTABILE,
            premi_lotterie=PREMI,
            letto_alle=timezone.now(),
        )
        testo = testo_telegram(row)
        self.assertIn('🎱 <b>Lotto</b>', testo)
        self.assertIn('409,50 €', testo)
        self.assertIn('127,50 €', testo)
        self.assertIn('249,24 €', testo)
        self.assertIn('Lotto 86,00', testo)
        self.assertIn('10eLotto 314,50', testo)
        self.assertIn('🎟️ <b>Premi Gratta pagati</b>: <b>86,00 €</b> (10)', testo)


@patch.dict('os.environ', ENV)
class LeggiPortaleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Portale')

    @patch('reconciliation.portale_giornata.get_premi_pagati', return_value=PREMI)
    @patch('reconciliation.portale_giornata.get_contabile_lotto', return_value=CONTABILE)
    def test_salva_giornata(self, _c, _p):
        row = leggi_portale(self.company, date(2026, 11, 21))
        self.assertEqual(row.contabile_lotto['entrate'], 409.5)
        self.assertEqual(row.premi_lotterie['totale']['importo'], 86.0)
        self.assertEqual(row.errore, '')

    @patch('reconciliation.portale_giornata.get_premi_pagati', side_effect=PortaleServiceError('offline'))
    @patch('reconciliation.portale_giornata.get_contabile_lotto', side_effect=PortaleServiceError('offline'))
    def test_errore_non_blocca_salva_errore(self, _c, _p):
        row = leggi_portale(self.company, date(2026, 11, 21))
        self.assertIn('offline', row.errore)
        self.assertIsNone(row.contabile_lotto)
        self.assertIsNone(row.premi_lotterie)


@patch.dict('os.environ', ENV)
class ApiPortaleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='UI Portale')
        self.user = User.objects.create_user('op-port', password='secret', is_staff=True)
        self.client.login(username='op-port', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'a').hexdigest(),
            last_seen=timezone.now(),
        )

    @patch('reconciliation.portale_giornata.get_premi_pagati', return_value=PREMI)
    @patch('reconciliation.portale_giornata.get_contabile_lotto', return_value=CONTABILE)
    def test_post_rileggi(self, _c, _p):
        TabaUnoRequest.objects.create(
            company=self.company,
            date=date(2026, 11, 21),
            tipo=TabaUnoRequest.TIPO_CHIUSURA,
            status=TabaUnoRequest.DONE,
            payload={
                'voci': [
                    {'reparto': '301', 'descrizione': 'INCASSO LOTTO/10&LOTTO', 'entrate': 409.5, 'uscite': 0},
                    {'reparto': '300', 'descrizione': 'VINCITE GRATTA E VINCI', 'entrate': 0, 'uscite': 86.0},
                ],
            },
        )
        r = self.client.post(
            '/api/portale/giornata/',
            data=json.dumps({'data': '2026-11-21'}),
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['lotto']['entrate'], 409.5)
        self.assertEqual(data['riconciliazione']['lotto_entrate']['stato'], 'ok')

    @patch('reconciliation.portale_giornata.get_premi_pagati', side_effect=PortaleServiceError('offline'))
    @patch('reconciliation.portale_giornata.get_contabile_lotto', side_effect=PortaleServiceError('offline'))
    def test_chiusura_tabauno_non_bloccata_da_portale(self, _c, _p):
        agent = TabaUnoAgent.objects.get(company=self.company)
        agent.token_hash = hashlib.sha256(b'token-agente').hexdigest()
        agent.save(update_fields=['token_hash'])
        row = TabaUnoRequest.objects.create(
            company=self.company,
            date=date(2026, 11, 21),
            tipo=TabaUnoRequest.TIPO_CHIUSURA,
            status=TabaUnoRequest.PROCESSING,
        )
        r = self.client.post(
            f'/api/tabauno/agent/result/{row.id}/',
            data=json.dumps({'ok': True, 'payload': {'voci': [], 'verifiche': {}}}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer token-agente',
        )
        self.assertEqual(r.status_code, 200)
        row.refresh_from_db()
        self.assertEqual(row.status, TabaUnoRequest.DONE)
        giornata = PortaleGiornata.objects.get(company=self.company, data=date(2026, 11, 21))
        self.assertIn('offline', giornata.errore)


@patch.dict('os.environ', ENV)
class ApiN8nPortaleTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='N8N Portale')
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(b'x').hexdigest(),
            last_seen=timezone.now(),
        )

    def _post(self, token=TOKEN, body=None):
        return self.client.post(
            '/api/n8n/portale/giornata/',
            data=json.dumps(body if body is not None else {'company_id': self.company.id, 'data': '2026-11-21'}),
            content_type='application/json',
            HTTP_X_N8N_TOKEN=token,
        )

    def test_auth_401(self):
        r = self._post(token='sbagliato')
        self.assertEqual(r.status_code, 401)

    @patch('reconciliation.n8n_portale_views.leggi_portale', side_effect=PortaleServiceError('PC offline'))
    def test_errore_200_con_testo(self, _leggi):
        r = self._post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('non disponibili', data['testo'])
        self.assertIn('PC offline', data['testo'])

    @patch('reconciliation.portale_giornata.get_premi_pagati', return_value=PREMI)
    @patch('reconciliation.portale_giornata.get_contabile_lotto', return_value=CONTABILE)
    def test_ok(self, _c, _p):
        r = self._post()
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['lotto']['saldo'], 249.24)
        self.assertEqual(data['premi_lotterie']['totale']['importo'], 86.0)
        self.assertIn('Premi Gratta pagati', data['testo'])
