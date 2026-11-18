import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.models import Company, TabacchiPreordine, TabaUnoRequest
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from reconciliation.tabacchi_preordine import (
    calcola_righe,
    codice_aams_logista,
    famiglia_da_categoria,
    find_soffice,
    giorni_alla_consegna,
    logista_xls_bytes,
    media_riferimento,
    normalizza_scorta_pct,
    proiezione_dopo_ordine,
    prossimo_giorno_consegna,
    proposta_unita,
    quantita_logista,
    righe_export_logista,
    unita_ordine,
    unita_ordine_dispositivo,
    workbook_stream_ends_at_eof,
)

FIXTURE_ORDINE = (
    Path(__file__).resolve().parent / 'fixtures' / 'Ordine_Logista01-04-2026-09-37-16.xls'
)
HAS_SOFFICE = find_soffice() is not None
SKIP_NO_SOFFICE = 'LibreOffice (soffice) non installato: test conversione Ordine_Logista.xls saltato.'


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

    def test_dispositivi_e_solidi_in_confezioni(self):
        self.assertEqual(famiglia_da_categoria('SIGARETTE ELETTRONICHE'), 'Dispositivi')
        self.assertEqual(
            famiglia_da_categoria('PRODOTTI SENZA COMBUSTIONE - SOLIDI DIVERSI DA TABACCO'),
            'Solidi',
        )
        pezzi, kg = unita_ordine_dispositivo(10)
        self.assertEqual(pezzi, 10)
        self.assertEqual(kg, 0)
        ultimo = date(2026, 11, 16)
        aperture = [(ultimo - timedelta(days=i)).isoformat() for i in range(0, 14)]
        dati = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': aperture,
            'articoli': [{
                'aams': 'K0011',
                'descrizione': '11 - LEVIA RUBY WALTZ',
                'categoria': 'PRODOTTI SENZA COMBUSTIONE - SOLIDI DIVERSI DA TABACCO',
                'tipo': 'dispositivo',
                'prezzo': 5.5,
                'prezzo_kg': 0,
                'minimo_grammi': 1,
                'pacstecca': 10,
                'giacenza': 5,
                'vendite_giornaliere': {day: 2 for day in aperture},
                'giacenze_fine_giorno': {},
            }],
        }
        righe, scartati = calcola_righe(
            dati,
            date(2026, 11, 17),
            giorni_copertura=7,
            data_consegna=date(2026, 11, 23),
            scorta_pct=200,
        )
        self.assertEqual(scartati, [])
        self.assertEqual(righe[0]['famiglia'], 'Solidi')
        self.assertEqual(righe[0]['pacchetti_per_unita'], 10)
        self.assertEqual(righe[0]['kg_per_unita'], 0)
        self.assertGreater(righe[0]['unita'], 0)

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

    def test_patch_conserva_correzioni_e_xls_logista(self):
        lettura = self._lettura_pronta()
        creato = self.client.post(
            f'/api/tabacchi/preordini/da-richiesta/{lettura.id}/',
            data='{"giorni_copertura":7,"data_consegna":"2026-11-23"}',
            content_type='application/json',
        )
        preordine = creato.json()['preordine']
        riga = next(r for r in preordine['righe'] if r['aams'] == '201')
        forzata = max(1, int(riga['unita_proposte']) + 2)
        aggiorna = self.client.patch(
            f"/api/tabacchi/preordini/{preordine['id']}/",
            data=f'{{"giorni_copertura":14,"scorta_pct":80,"righe":[{{"aams":"201","unita":{forzata}}}]}}',
            content_type='application/json',
        )
        self.assertEqual(aggiorna.status_code, 200)
        aggiornato = aggiorna.json()['preordine']
        riga2 = next(r for r in aggiornato['righe'] if r['aams'] == '201')
        self.assertEqual(riga2['unita'], forzata)
        self.assertTrue(riga2['corretto_a_mano'])
        self.assertEqual(aggiornato['giorni_copertura'], 14)
        self.assertEqual(aggiornato['scorta_pct'], 80)

        fake_xls = FIXTURE_ORDINE.read_bytes() if FIXTURE_ORDINE.is_file() else b'\xd0\xcf\x11\xe0fake'
        with patch('reconciliation.tabacchi_views.logista_xls_bytes', return_value=fake_xls):
            import xlrd
            for path in ('csv', 'logista'):
                resp = self.client.get(f"/api/tabacchi/preordini/{preordine['id']}/{path}/")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp['Content-Type'], 'application/vnd.ms-excel')
                self.assertIn('Ordine_Logista.xls', resp['Content-Disposition'])
                self.assertTrue(resp.content.startswith(b'\xd0\xcf\x11\xe0'))
                if FIXTURE_ORDINE.is_file():
                    sheet = xlrd.open_workbook(file_contents=resp.content).sheet_by_index(0)
                    self.assertEqual(sheet.name, 'Foglio1')
                    self.assertEqual(sheet.cell_value(0, 0), 'Codice AAMS')
                    self.assertEqual(sheet.cell_value(0, 1), 'Quantita')

        eliminato = self.client.delete(f"/api/tabacchi/preordini/{preordine['id']}/")
        self.assertEqual(eliminato.status_code, 200)
        self.assertEqual(TabacchiPreordine.objects.filter(id=preordine['id']).count(), 0)

    def test_proiezione_dopo_ordine_residuo(self):
        # giac 8, media 2.3, 5 gg alla consegna → alla=0; +3 stecche×10=30; dopo 7gg ≈ 13.9
        out = proiezione_dopo_ordine(
            Decimal('2.3'), 8, 10, 3, 5, 7, date(2026, 11, 23),
        )
        self.assertEqual(out['giacenza_dopo_consegna'], Decimal('30'))
        self.assertAlmostEqual(float(out['residuo_copertura']), 13.9, places=1)
        self.assertEqual(out['urgenza_copertura'], 'normale')
        self.assertEqual(out['data_copre_fino'], date(2026, 12, 6))
        sotto = proiezione_dopo_ordine(
            Decimal('2.3'), 8, 10, 0, 5, 7, date(2026, 11, 23),
        )
        self.assertLess(sotto['residuo_copertura'], 0)
        self.assertEqual(sotto['urgenza_copertura'], 'rossa')

    def test_export_logista_formato_righe(self):
        self.assertEqual(codice_aams_logista('201'), '0201')
        self.assertEqual(codice_aams_logista('21108'), '21108')
        self.assertEqual(codice_aams_logista('V0PYU'), 'V0PYU')
        self.assertEqual(quantita_logista(7, '0.200', 'Sigarette'), '1,4')
        self.assertEqual(quantita_logista(2, '0', 'Dispositivi', 'dispositivo'), '2')
        payload = [
            {'aams': '201', 'unita': 7, 'kg_per_unita': '0.200', 'famiglia': 'Sigarette'},
            {'aams': 'V0PYU', 'unita': 2, 'kg_per_unita': 0, 'famiglia': 'Dispositivi', 'tipo': 'dispositivo'},
            {'aams': '999', 'unita': 0, 'kg_per_unita': '0.200', 'famiglia': 'Sigarette'},
        ]
        self.assertEqual(righe_export_logista(payload), [('0201', '1,4'), ('V0PYU', '2')])

    @skipUnless(HAS_SOFFICE, SKIP_NO_SOFFICE)
    def test_export_logista_libreoffice_struttura(self):
        import olefile
        import xlrd

        self.assertTrue(FIXTURE_ORDINE.is_file(), 'Manca fixture Ordine_Logista originale TabaUno')
        fixture = FIXTURE_ORDINE.read_bytes()
        ole_fix = olefile.OleFileIO(io.BytesIO(fixture))
        self.assertIn(('\x05SummaryInformation',), {tuple(s) for s in ole_fix.listdir()})
        ole_fix.close()
        self.assertTrue(workbook_stream_ends_at_eof(fixture))

        payload = [
            {'aams': '201', 'unita': 7, 'kg_per_unita': '0.200', 'famiglia': 'Sigarette'},
            {'aams': '176', 'unita': 2, 'kg_per_unita': '0.200', 'famiglia': 'Sigarette'},
            {'aams': 'K0011', 'unita': 1, 'kg_per_unita': 0, 'famiglia': 'Dispositivi', 'tipo': 'dispositivo'},
            {'aams': 'VA0QP', 'unita': 2, 'kg_per_unita': 0, 'famiglia': 'Dispositivi', 'tipo': 'dispositivo'},
        ]
        # 100+ righe con zeri iniziali / decimali misti
        for index in range(100):
            payload.append({
                'aams': str(index + 1),
                'unita': (index % 5) + 1,
                'kg_per_unita': '0.200',
                'famiglia': 'Sigarette',
            })
        expected = dict(righe_export_logista(payload))
        raw = logista_xls_bytes(payload)
        self.assertTrue(raw.startswith(b'\xd0\xcf\x11\xe0'))

        ole = olefile.OleFileIO(io.BytesIO(raw))
        streams = {tuple(s) for s in ole.listdir()}
        ole.close()
        self.assertIn(('Workbook',), streams)
        self.assertIn(('\x05SummaryInformation',), streams)
        self.assertTrue(
            workbook_stream_ends_at_eof(raw),
            'Workbook ha byte in coda dopo EOF (come i file xlwt)',
        )

        book = xlrd.open_workbook(file_contents=raw)
        self.assertEqual(book.biff_version, 80)
        self.assertEqual(book.nsheets, 1)
        sheet = book.sheet_by_index(0)
        self.assertEqual(sheet.name, 'Foglio1')
        self.assertEqual(sheet.cell_value(0, 0), 'Codice AAMS')
        self.assertEqual(sheet.cell_value(0, 1), 'Quantita')
        self.assertEqual(sheet.cell(0, 0).ctype, 1)
        self.assertEqual(sheet.cell(0, 1).ctype, 1)
        self.assertGreaterEqual(sheet.nrows, 105)
        for row in range(1, sheet.nrows):
            codice = sheet.cell_value(row, 0)
            quantita = sheet.cell_value(row, 1)
            self.assertEqual(sheet.cell(row, 0).ctype, 1, msg=repr(codice))
            self.assertEqual(sheet.cell(row, 1).ctype, 1, msg=repr(quantita))
            self.assertIn(codice, expected)
            self.assertEqual(quantita, expected[codice])
        self.assertEqual(sheet.cell_value(1, 0), '0201')
        self.assertEqual(sheet.cell_value(1, 1), '1,4')

    def test_deposita_tabauno_accoda_e_agente_scarica(self):
        import hashlib

        from reconciliation.models import TabaUnoAgent
        from reconciliation.tabauno_portal import claim_next_request

        lettura = self._lettura_pronta()
        creato = self.client.post(
            f'/api/tabacchi/preordini/da-richiesta/{lettura.id}/',
            data='{"giorni_copertura":7,"data_consegna":"2026-11-23"}',
            content_type='application/json',
        )
        preordine_id = creato.json()['preordine']['id']
        # Forza almeno una quantità > 0
        self.client.patch(
            f'/api/tabacchi/preordini/{preordine_id}/',
            data='{"righe":[{"aams":"201","unita":3}]}',
            content_type='application/json',
        )

        offline = self.client.post(f'/api/tabacchi/preordini/{preordine_id}/deposita-tabauno/')
        self.assertEqual(offline.status_code, 409)

        token = 'agent-deposit-test'
        TabaUnoAgent.objects.create(
            company=self.company,
            token_hash=hashlib.sha256(token.encode()).hexdigest(),
            last_seen=timezone.now(),
        )
        accodata = self.client.post(f'/api/tabacchi/preordini/{preordine_id}/deposita-tabauno/')
        self.assertEqual(accodata.status_code, 201)
        request_id = accodata.json()['id']
        di_nuovo = self.client.post(f'/api/tabacchi/preordini/{preordine_id}/deposita-tabauno/')
        self.assertEqual(di_nuovo.status_code, 200)
        self.assertEqual(di_nuovo.json()['id'], request_id)

        claimed = claim_next_request(self.company)
        self.assertEqual(claimed.id, request_id)
        self.assertEqual(claimed.tipo, TabaUnoRequest.TIPO_DEPOSITA_ORDINE_LOGISTA)

        fake_xls = FIXTURE_ORDINE.read_bytes() if FIXTURE_ORDINE.is_file() else b'\xd0\xcf\x11\xe0fake'
        with patch('reconciliation.tabacchi_preordine.logista_xls_bytes', return_value=fake_xls):
            file_resp = self.client.get(
                f'/api/tabauno/agent/ordine-logista/{request_id}/',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
        self.assertEqual(file_resp.status_code, 200)
        self.assertTrue(file_resp.content.startswith(b'\xd0\xcf\x11\xe0'))

        result = self.client.post(
            f'/api/tabauno/agent/result/{request_id}/',
            data=(
                '{"ok":true,"payload":{"ok":true,"verificato":true,'
                '"path":"C:\\\\Users\\\\Public\\\\TabaUno\\\\Ordine_Logista.xls",'
                '"bytes":124416,"messaggio":"Ordine_Logista.xls generato correttamente"}}'
            ),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(result.status_code, 200)
        row = TabaUnoRequest.objects.get(id=request_id)
        self.assertEqual(row.status, TabaUnoRequest.DONE)
        self.assertTrue(row.payload.get('verificato'))
        self.assertIn('generato correttamente', row.payload.get('messaggio', ''))
        preordine = TabacchiPreordine.objects.get(id=preordine_id)
        self.assertEqual(preordine.stato, TabacchiPreordine.ESPORTATO)

        # Payload incompleto → non si considera generato
        altra = TabaUnoRequest.objects.create(
            company=self.company,
            date=timezone.localdate(),
            tipo=TabaUnoRequest.TIPO_DEPOSITA_ORDINE_LOGISTA,
            status=TabaUnoRequest.PROCESSING,
            parametri={'preordine_id': preordine_id},
            picked_at=timezone.now(),
        )
        bad = self.client.post(
            f'/api/tabauno/agent/result/{altra.id}/',
            data='{"ok":true,"payload":{"path":"","bytes":0}}',
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        self.assertEqual(bad.status_code, 200)
        altra.refresh_from_db()
        self.assertEqual(altra.status, TabaUnoRequest.ERROR)
