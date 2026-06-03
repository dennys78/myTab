from decimal import Decimal

from django.test import SimpleTestCase

from reconciliation.draft_notifications import build_closure_incasso_summary
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
        self.assertEqual(result['totale'], 1650.0)
        self.assertEqual(result['differenza'], -12.5)
