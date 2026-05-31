from decimal import Decimal

from django.test import SimpleTestCase

from reconciliation.views import _reconcile_totale_cassa


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
