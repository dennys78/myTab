import json
import os
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from reconciliation.draft_notifications import build_closure_incasso_summary
from reconciliation.telegram_fondo_cassa import parse_fondo_command, parse_preleva_destinazione
from reconciliation.views import _calc_closure_differenza, _reconcile_totale_cassa


class ReconcileTotaleCassaTests(SimpleTestCase):
    def test_zero_totale_uses_saldo_reparti(self):
        items = [
            {'entrate': 1000, 'uscite': 50},
            {'entrate': 500, 'uscite': 0},
        ]
        summary = {
            'contanti': 400,
            'pag_pos': 600,
            'cassa_auto': 0,
            'reso_cont': 0,
            'reso_auto': 0,
            'distrib': 450,
            'totale': 0,
        }
        result = _reconcile_totale_cassa(summary, items)
        self.assertEqual(result, Decimal('1450.00'))

    def test_totale_equals_pag_pos_corrected(self):
        items = [{'entrate': 2000, 'uscite': 100}]
        summary = {
            'contanti': 500,
            'pag_pos': 650,
            'cassa_auto': 0,
            'reso_cont': 0,
            'reso_auto': 0,
            'distrib': 750,
            'totale': 650,
        }
        result = _reconcile_totale_cassa(summary, items)
        self.assertEqual(result, Decimal('1900.00'))

    def test_valid_totale_kept(self):
        items = [{'entrate': 800, 'uscite': 0}]
        summary = {
            'contanti': 300,
            'pag_pos': 500,
            'cassa_auto': 0,
            'reso_cont': 0,
            'reso_auto': 0,
            'distrib': 0,
            'totale': 800,
        }
        result = _reconcile_totale_cassa(summary, items)
        self.assertEqual(result, Decimal('800.00'))


class CalcClosureDifferenzaTests(SimpleTestCase):
    def test_cassetto_mode(self):
        items = [{'entrate': 100, 'uscite': 0}]
        diff, tc = _calc_closure_differenza(
            Decimal('1000'),
            Decimal('200'),
            Decimal('50'),
            Decimal('0'),
            Decimal('0'),
            items,
            with_reports=False,
            totale_scassettato=Decimal('800'),
        )
        self.assertEqual(diff, Decimal('50.00'))
        self.assertEqual(tc, Decimal('800.00'))

    def test_report_mode(self):
        items = [
            {'entrate': 665, 'uscite': 283},
            {'entrate': 100, 'uscite': 10},
        ]
        diff, tc = _calc_closure_differenza(
            Decimal('1000'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            Decimal('0'),
            items,
            with_reports=True,
        )
        self.assertEqual(diff, Decimal('528.00'))
        self.assertEqual(tc, Decimal('0.00'))


class TelegramVersamentoParserTests(SimpleTestCase):
    def test_parse_with_amount_synonyms(self):
        from reconciliation.telegram_versamento import parse_versamento_message
        cases = [
            ('Versati 2343,20', 2343.20),
            ('versato 100', 100.0),
            ('versamento 500', 500.0),
            ('versamenti 1200,50', 1200.50),
            ('versamento in banca 800', 800.0),
            ('versato in banca 250,75', 250.75),
            ('deposito banca 400', 400.0),
            ('Versamento banca 99', 99.0),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                result = parse_versamento_message(text)
                self.assertEqual(result, {'importo': expected})

    def test_keyword_only_needs_amount(self):
        from reconciliation.telegram_versamento import parse_versamento_message
        for text in ('versamenti', 'versamento', 'versati', 'versato', 'deposito banca'):
            with self.subTest(text=text):
                self.assertEqual(parse_versamento_message(text), {'needs_amount': True})

    def test_ambiguous_versamento(self):
        from reconciliation.telegram_versamento import parse_versamento_message
        self.assertEqual(parse_versamento_message('versamento ieri'), {'ambiguous': True})
        self.assertIsNone(parse_versamento_message('Distributore 505'))

    def test_invalid_amount_is_ambiguous(self):
        from reconciliation.telegram_versamento import parse_versamento_message
        result = parse_versamento_message('versati abc')
        self.assertTrue(result.get('ambiguous'))


class TelegramSpicciParserTests(SimpleTestCase):
    def test_parse_with_amount(self):
        from reconciliation.telegram_spicci import TIPO_USCITA, parse_spicci_message
        cases = [
            ('Spicci 50', 50.0, 'Spicci'),
            ('monete 25,50', 25.5, 'Monete'),
            ('Monetine 10', 10.0, 'Monetine'),
            ('spiccioli 100', 100.0, 'Spicci'),
        ]
        for text, amount, desc in cases:
            with self.subTest(text=text):
                result = parse_spicci_message(text)
                self.assertEqual(result['importo'], amount)
                self.assertEqual(result['descrizione'], desc)
                self.assertEqual(result['tipo'], TIPO_USCITA)

    def test_keyword_only(self):
        from reconciliation.telegram_spicci import parse_spicci_message
        self.assertEqual(
            parse_spicci_message('monete'),
            {'needs_amount': True, 'descrizione': 'Monete'},
        )

    def test_not_parsed_as_entrata(self):
        from reconciliation.telegram_movimenti import parse_movimento_entrata_message
        self.assertIsNone(parse_movimento_entrata_message('Spicci 50'))
        self.assertIsNone(parse_movimento_entrata_message('monetine 20'))


class TelegramMovimentoVersamentoTests(SimpleTestCase):
    def test_versati_not_parsed_as_entrata(self):
        from reconciliation.telegram_movimenti import parse_movimento_entrata_message
        self.assertIsNone(parse_movimento_entrata_message('Versati 100'))
        self.assertIsNone(parse_movimento_entrata_message('Versato 2343,20'))
        self.assertIsNone(parse_movimento_entrata_message('Versamento 100'))
        self.assertIsNone(parse_movimento_entrata_message('versamenti 50'))


class TelegramFondoCommandTests(SimpleTestCase):
    def test_parse_aggiungi_fondo(self):
        kind, amount = parse_fondo_command('aggiungi a fondo 200')
        self.assertEqual(kind, 'aggiungi')
        self.assertEqual(amount, 200.0)

    def test_parse_preleva_fondo_with_comma(self):
        kind, amount = parse_fondo_command('preleva da fondo (50,25)')
        self.assertEqual(kind, 'preleva')
        self.assertEqual(amount, 50.25)

    def test_parse_unknown_returns_none(self):
        self.assertIsNone(parse_fondo_command('Versati 100'))

    def test_parse_preleva_destinazione(self):
        self.assertEqual(parse_preleva_destinazione('personale'), 'personale')
        self.assertEqual(parse_preleva_destinazione('contanti in cassa'), 'cassa')
        self.assertIsNone(parse_preleva_destinazione('altro'))


class ClosureIncassoSummaryTests(SimpleTestCase):
    def test_summary_tabacchi_gratta_totale(self):
        items = [
            {'descrizione': 'TABACCHI', 'entrate': 1200, 'uscite': 0},
            {'descrizione': 'GRATTA E VINCI', 'entrate': 350, 'uscite': 50},
            {'descrizione': 'CAFFÈ', 'entrate': 100, 'uscite': 0},
        ]
        summary = {'differenza': -12.5}
        result = build_closure_incasso_summary(items, summary)
        self.assertEqual(result['tabacchi'], 1200.0)
        self.assertEqual(result['gratta'], 350.0)
        self.assertEqual(result['differenza'], -12.5)


class TabaUnoImportTests(TestCase):
    def setUp(self):
        from reconciliation.models import Company
        self.company = Company.objects.create(denominazione='Tabacchi')
        self.payload = {
            'data': '2026-11-16',
            'company_id': self.company.id,
            'voci': [
                {'reparto': '01', 'descrizione': 'TABACCHI', 'entrate': 1582.70, 'uscite': 0, 'saldo': 1582.70},
            ],
            'totale': {'entrate': 3302.50, 'uscite': 446.70, 'saldo': 2855.80},
            'incasso': {'pos': 699.70, 'contanti': 2156.10, 'totale': 2855.80},
            'verifiche': {'saldo_uguale_incasso': True},
        }
        self._previous = os.environ.get('TABAUNO_IMPORT_TOKEN')
        os.environ['TABAUNO_IMPORT_TOKEN'] = 'secret-token'

    def tearDown(self):
        if self._previous is None:
            os.environ.pop('TABAUNO_IMPORT_TOKEN', None)
        else:
            os.environ['TABAUNO_IMPORT_TOKEN'] = self._previous

    def _post(self, token='secret-token'):
        return self.client.post(
            '/api/closures/import-tabauno/',
            data=json.dumps(self.payload),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

    def test_creates_once_and_leaves_manual_fields_empty(self):
        from reconciliation.models import CashClosure
        created = self._post()
        self.assertEqual(created.status_code, 201)
        body = created.json()
        self.assertTrue(body['created'])
        closure = CashClosure.objects.get(id=body['id'])
        self.assertEqual(closure.operator, 'TabaUno')
        self.assertEqual(closure.contanti, Decimal('2156.10'))
        self.assertEqual(closure.pag_pos, Decimal('699.70'))
        self.assertEqual(closure.totale_generale, Decimal('2855.80'))
        self.assertEqual(closure.cassa_auto, Decimal('0.00'))
        self.assertEqual(closure.reso_cont, Decimal('0.00'))
        self.assertEqual(closure.distrib, Decimal('0.00'))
        self.assertEqual(closure.items.get().department_name, 'TABACCHI')

        again = self._post()
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.json()['status'], 'exists')
        self.assertEqual(again.json()['id'], closure.id)
        self.assertEqual(CashClosure.objects.filter(company=self.company, date='2026-11-16').count(), 1)

    def test_rejects_missing_token(self):
        denied = self._post(token='altro')
        self.assertEqual(denied.status_code, 401)
