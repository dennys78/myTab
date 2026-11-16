import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

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


class TabaUnoQueueTests(TestCase):
    def setUp(self):
        from reconciliation.models import Company, TabaUnoAgent
        from reconciliation.tabauno_portal import _digest
        self.company = Company.objects.create(denominazione='Tabacchi')
        self.other = Company.objects.create(denominazione='Altra')
        self.user = User.objects.create_user('operatore', password='secret', is_staff=True)
        self.token = 'agent-secret'
        TabaUnoAgent.objects.create(company=self.company, token_hash=_digest(self.token))
        self.client.login(username='operatore', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()

    def _queue(self, day='2026-11-16'):
        return self.client.post(
            '/api/tabauno/requests/',
            data=json.dumps({'date': day}),
            content_type='application/json',
        )

    def test_create_and_deduplicate(self):
        first = self._queue()
        self.assertEqual(first.status_code, 201)
        second = self._queue()
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()['created'])
        self.assertEqual(first.json()['id'], second.json()['id'])

    def test_future_date_rejected(self):
        response = self._queue('2999-01-01')
        self.assertEqual(response.status_code, 400)

    def test_next_empty_then_claim_once(self):
        empty = self.client.get(
            '/api/tabauno/agent/next/',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(empty.status_code, 204)
        queued = self._queue()
        request_id = queued.json()['id']
        first = self.client.get(
            '/api/tabauno/agent/next/',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        second = self.client.get(
            '/api/tabauno/agent/next/',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['id'], request_id)
        self.assertEqual(second.status_code, 204)
        self.assertNotEqual(getattr(second, 'content', b''), first.content)

    def test_two_pending_are_not_the_same_claim(self):
        first_id = self._queue('2026-11-15').json()['id']
        second_id = self._queue('2026-11-14').json()['id']
        claimed = []
        for _ in range(2):
            response = self.client.get(
                '/api/tabauno/agent/next/',
                HTTP_AUTHORIZATION=f'Bearer {self.token}',
            )
            self.assertEqual(response.status_code, 200)
            claimed.append(response.json()['id'])
        self.assertEqual(sorted(claimed), sorted([first_id, second_id]))
        self.assertEqual(len(set(claimed)), 2)

    def test_result_only_while_processing_and_same_company(self):
        from reconciliation.models import TabaUnoAgent, TabaUnoRequest
        from reconciliation.tabauno_portal import _digest
        request_id = self._queue().json()['id']
        too_soon = self.client.post(
            f'/api/tabauno/agent/result/{request_id}/',
            data=json.dumps({'ok': True, 'payload': {'data': '2026-11-16'}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(too_soon.status_code, 409)
        self.client.get('/api/tabauno/agent/next/', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        other_token = 'altro-agente'
        TabaUnoAgent.objects.create(company=self.other, token_hash=_digest(other_token))
        foreign = self.client.post(
            f'/api/tabauno/agent/result/{request_id}/',
            data=json.dumps({'ok': True, 'payload': {'data': '2026-11-16'}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {other_token}',
        )
        self.assertEqual(foreign.status_code, 409)
        done = self.client.post(
            f'/api/tabauno/agent/result/{request_id}/',
            data=json.dumps({'ok': True, 'payload': {'data': '2026-11-16', 'voci': []}}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {self.token}',
        )
        self.assertEqual(done.status_code, 200)
        self.assertEqual(TabaUnoRequest.objects.get(id=request_id).status, 'done')

    def test_bad_token_is_unauthorized(self):
        denied = self.client.get(
            '/api/tabauno/agent/next/',
            HTTP_AUTHORIZATION='Bearer no',
        )
        self.assertEqual(denied.status_code, 401)

    def test_pending_and_processing_expire(self):
        from reconciliation.models import TabaUnoRequest
        request_id = self._queue().json()['id']
        TabaUnoRequest.objects.filter(id=request_id).update(
            created_at=timezone.now() - timedelta(minutes=11),
        )
        detail = self.client.get(f'/api/tabauno/requests/{request_id}/')
        self.assertEqual(detail.json()['status'], 'expired')

        fresh = self._queue('2026-11-10')
        fresh_id = fresh.json()['id']
        self.client.get('/api/tabauno/agent/next/', HTTP_AUTHORIZATION=f'Bearer {self.token}')
        TabaUnoRequest.objects.filter(id=fresh_id).update(
            picked_at=timezone.now() - timedelta(minutes=6),
        )
        detail = self.client.get(f'/api/tabauno/requests/{fresh_id}/')
        self.assertEqual(detail.json()['status'], 'error')
        self.assertIn('non ha risposto', detail.json()['error'])

    def test_portal_post_without_csrf_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.login(username='operatore', password='secret')
        response = client.post(
            '/api/tabauno/requests/',
            data=json.dumps({'date': '2026-11-16'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
