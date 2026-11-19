from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.giacenze_stats import (
    ESAURITO,
    FERMO,
    OK,
    PRIMA_CONSEGNA,
    RISCHIO,
    calcola_giacenze,
    stato_giacenza,
    vendite_settimanali,
)
from reconciliation.models import Company, TabaUnoRequest


class FormulaGiacenzeTests(TestCase):
    def test_vendite_settimanali_quattro_blocchi(self):
        ultimo = date(2026, 11, 16)
        vendite = {
            (ultimo - timedelta(days=i)).isoformat(): 1 for i in range(28)
        }
        self.assertEqual(vendite_settimanali(vendite, ultimo), [Decimal(7)] * 4)

    def test_stati(self):
        self.assertEqual(stato_giacenza(0, 5, 6), ESAURITO)
        self.assertEqual(stato_giacenza(20, 5, 6), PRIMA_CONSEGNA)  # 4 giorni < 6
        self.assertEqual(stato_giacenza(35, 5, 6), RISCHIO)  # 7 giorni < 6+2
        self.assertEqual(stato_giacenza(50, 5, 6), OK)
        self.assertEqual(stato_giacenza(10, 0, 6), FERMO)

    def test_proiezione_a_data_scelta(self):
        ultimo = date(2026, 11, 16)
        aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 28)]
        dati = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': aperture,
            'articoli': [{
                'aams': '201',
                'descrizione': 'CHESTERFIELD',
                'categoria': 'SIGARETTE',
                'prezzo': 5.8,
                'prezzo_kg': 290,
                'minimo_grammi': 200,
                'giacenza': 40,
                'vendite_giornaliere': {day: 5 for day in aperture},
                'giacenze_fine_giorno': {},
            }, {
                'aams': '999',
                'descrizione': 'FERMO',
                'categoria': 'SIGARETTE',
                'prezzo': 5,
                'prezzo_kg': 250,
                'minimo_grammi': 200,
                'giacenza': 30,
                'vendite_giornaliere': {},
                'giacenze_fine_giorno': {},
            }],
        }
        oggi = date(2026, 11, 17)
        consegna = date(2026, 11, 23)
        analisi = calcola_giacenze(dati, oggi, consegna=consegna, data_proiezione=date(2026, 11, 20))
        self.assertEqual(analisi['giorni_alla_consegna'], 6)
        self.assertEqual(analisi['giorni_alla_proiezione'], 3)
        chester = next(r for r in analisi['righe'] if r['aams'] == '201')
        self.assertEqual(chester['alla_data'], 25.0)  # 40 - 5*3
        self.assertEqual(chester['alla_consegna'], 10.0)  # 40 - 5*6
        self.assertEqual(chester['stato'], OK)
        fermo = next(r for r in analisi['righe'] if r['aams'] == '999')
        self.assertEqual(fermo['stato'], FERMO)


class GiacenzeApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Giacenze')
        self.user = User.objects.create_user('op-gia', password='secret', is_staff=True)
        self.client.login(username='op-gia', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()

    def _payload(self):
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

    def test_analisi_dopo_lettura(self):
        lettura = TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
            status=TabaUnoRequest.DONE,
            payload=self._payload(),
            requested_by=self.user,
            completed_at=timezone.now(),
        )
        response = self.client.get(f'/api/statistiche/giacenze/?request_id={lettura.id}&data=2026-11-20')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['pronta'])
        self.assertEqual(body['analisi']['data_proiezione'], '2026-11-20')
        self.assertGreaterEqual(len(body['analisi']['righe']), 1)
        self.assertIn('alla_data', body['analisi']['righe'][0])

    def test_lettura_richiede_agente_online(self):
        response = self.client.post('/api/statistiche/giacenze/lettura/')
        self.assertEqual(response.status_code, 409)
