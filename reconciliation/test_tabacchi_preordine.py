import csv
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.models import Company, TabacchiPreordine, TabaUnoRequest
from reconciliation.tabacchi_preordine import (
    calcola_righe,
    giorni_alla_consegna,
    media_riferimento,
    normalizza_scorta_pct,
    prossimo_giorno_consegna,
    proposta_unita,
    unita_ordine,
)


ESEMPI = [
    ('2423', 'MERIT BAY KS DA 20 A.', Decimal('7.33'), 40, 10, 6),
    ('20659', 'TEREA AZURE DA 20', Decimal('6.70'), 45, 10, 5),
    ('21108', 'DELIA CLASSIC GOLD DA 20', Decimal('7.02'), 54, 10, 4),
    ('201', 'CHESTERFIELD BLUE KS DA 20 A.', Decimal('9.40'), 96, 10, 3),
]


class FormulaTabacchiTests(TestCase):
    def test_giorni_alla_consegna_sei(self):
        self.assertEqual(
            giorni_alla_consegna(date(2026, 11, 17), date(2026, 11, 16), date(2026, 11, 23)),
            6,
        )

    def test_prossimo_lunedi(self):
        self.assertEqual(prossimo_giorno_consegna(date(2026, 11, 17), 0), date(2026, 11, 23))

    def test_unita_ordine_sigarette_e_minimi_diversi(self):
        u, kg = unita_ordine(5.8, 290, 200)
        self.assertEqual(u, 10)
        self.assertEqual(kg, Decimal('0.200'))
        u300, kg300 = unita_ordine(10, 200, 300)
        self.assertEqual(u300, 6)
        self.assertEqual(kg300, Decimal('0.300'))
        u500, kg500 = unita_ordine(8, 160, 500)
        self.assertEqual(u500, 10)
        self.assertEqual(kg500, Decimal('0.500'))

    def test_righe_di_esempio_a_sette_giorni(self):
        for _aams, _nome, media, giacenza, u, atteso in ESEMPI:
            proposta = proposta_unita(media, giacenza, u, 7, 6, 100)
            self.assertEqual(proposta['unita'], atteso, msg=_nome)

    def test_scorta_pct_scala_la_proposta(self):
        self.assertEqual(normalizza_scorta_pct(5), 10)
        self.assertEqual(normalizza_scorta_pct(300), 250)
        base = proposta_unita(Decimal('9.40'), 96, 10, 7, 6, 100)
        meta = proposta_unita(Decimal('9.40'), 96, 10, 7, 6, 50)
        piena = proposta_unita(Decimal('9.40'), 96, 10, 7, 6, 200)
        self.assertEqual(base['unita'], 3)
        self.assertLess(meta['unita'], base['unita'])
        self.assertGreaterEqual(piena['unita'], base['unita'])

    def test_media_esclude_giorni_esauriti_e_pesa_3_2_1(self):
        ultimo = date(2026, 11, 16)
        vendite = {
            ultimo.isoformat(): 6,
            (ultimo - timedelta(days=10)).isoformat(): 4,
            (ultimo - timedelta(days=20)).isoformat(): 2,
            (ultimo - timedelta(days=3)).isoformat(): 1,
        }
        giacenze = {
            (ultimo - timedelta(days=4)).isoformat(): 1,
        }
        aperture = list(vendite)
        media, esclusi = media_riferimento(vendite, giacenze, aperture, ultimo, 10)
        self.assertEqual(esclusi, 1)
        self.assertEqual(media, Decimal('28') / Decimal('6'))

    def test_calcola_righe_sintetiche(self):
        ultimo = date(2026, 11, 16)
        aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 21, 1)]
        vendite = {day: 5 for day in aperture}
        dati = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': aperture,
            'articoli': [{
                'aams': '201',
                'descrizione': 'CHESTERFIELD BLUE KS DA 20 A.',
                'categoria': 'SIGARETTE',
                'prezzo': 5.8,
                'prezzo_kg': 290,
                'minimo_grammi': 200,
                'giacenza': 20,
                'vendite_giornaliere': vendite,
                'giacenze_fine_giorno': {},
            }],
        }
        righe, scartati = calcola_righe(
            dati,
            date(2026, 11, 17),
            giorni_copertura=7,
            data_consegna=date(2026, 11, 23),
        )
        self.assertEqual(scartati, [])
        self.assertEqual(len(righe), 1)
        self.assertEqual(righe[0]['pacchetti_per_unita'], 10)
        self.assertGreater(righe[0]['unita'], 0)
        self.assertEqual(righe[0]['famiglia'], 'Sigarette')


class TabacchiApiTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(denominazione='Tabaccheria Test')
        self.user = User.objects.create_user('op-tab', password='secret', is_staff=True)
        self.client.login(username='op-tab', password='secret')
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
            }, {
                'aams': '999',
                'descrizione': 'SENZA PARAMETRI',
                'categoria': 'SIGARETTE',
                'prezzo': 0,
                'prezzo_kg': 0,
                'minimo_grammi': 0,
                'giacenza': 10,
                'vendite_giornaliere': {aperture[0]: 1},
                'giacenze_fine_giorno': {},
            }],
        }

    def _lettura_pronta(self):
        return TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
            status=TabaUnoRequest.DONE,
            payload=self._payload(),
            requested_by=self.user,
        )

    def test_crea_richiesta_e_preordine(self):
        creata = self.client.post('/api/tabacchi/preordini/', data='{}', content_type='application/json')
        self.assertEqual(creata.status_code, 201)
        request_id = creata.json()['id']
        di_nuovo = self.client.post('/api/tabacchi/preordini/', data='{}', content_type='application/json')
        self.assertEqual(di_nuovo.json()['id'], request_id)
        lettura = TabaUnoRequest.objects.get(id=request_id)
        lettura.status = TabaUnoRequest.DONE
        lettura.payload = self._payload()
        lettura.save()
        preordine = self.client.post(
            f'/api/tabacchi/preordini/da-richiesta/{request_id}/',
            data='{"giorni_copertura":7,"data_consegna":"2026-11-23"}',
            content_type='application/json',
        )
        self.assertEqual(preordine.status_code, 201)
        body = preordine.json()['preordine']
        self.assertEqual(body['giorni_copertura'], 7)
        self.assertEqual(body['scorta_pct'], 200)
        self.assertTrue(any(r['aams'] == '201' for r in body['righe']))
        self.assertFalse(any(r['aams'] == '999' for r in body['righe']))

    def test_patch_conserva_correzioni_e_csv(self):
        lettura = self._lettura_pronta()
        creato = self.client.post(
            f'/api/tabacchi/preordini/da-richiesta/{lettura.id}/',
            data='{"giorni_copertura":7,"data_consegna":"2026-11-23"}',
            content_type='application/json',
        )
        preordine = creato.json()['preordine']
        riga = next(r for r in preordine['righe'] if r['aams'] == '201')
        forzata = max(1, int(riga['unita_proposte']) + 2)
        patch = self.client.patch(
            f"/api/tabacchi/preordini/{preordine['id']}/",
            data=f'{{"giorni_copertura":14,"scorta_pct":80,"righe":[{{"aams":"201","unita":{forzata}}}]}}',
            content_type='application/json',
        )
        self.assertEqual(patch.status_code, 200)
        aggiornato = patch.json()['preordine']
        riga2 = next(r for r in aggiornato['righe'] if r['aams'] == '201')
        self.assertEqual(riga2['unita'], forzata)
        self.assertTrue(riga2['corretto_a_mano'])
        self.assertEqual(aggiornato['giorni_copertura'], 14)
        self.assertEqual(aggiornato['scorta_pct'], 80)

        csv_resp = self.client.get(f"/api/tabacchi/preordini/{preordine['id']}/csv/")
        self.assertEqual(csv_resp.status_code, 200)
        text = csv_resp.content.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(text), delimiter=';')
        header = next(reader)
        self.assertEqual(header, [
            'codice_aams', 'descrizione', 'famiglia', 'stecche_o_confezioni', 'pacchetti', 'kg', 'importo',
        ])
        row = next(reader)
        self.assertEqual(row[0], '201')
        self.assertIn(',', row[5])
        self.assertIn(',', row[6])
        eliminato = self.client.delete(f"/api/tabacchi/preordini/{preordine['id']}/")
        self.assertEqual(eliminato.status_code, 200)
        self.assertEqual(TabacchiPreordine.objects.filter(id=preordine['id']).count(), 0)
