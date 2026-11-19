import hashlib
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from reconciliation.giacenze_report import (
    _parti_report,
    blocco_articolo,
    corpo_da_lettura,
    costruisci_testo,
    escape_html,
    formatta_data_corta,
    formatta_giorno_relativo,
    giacenza_mostrata,
    messaggio_indisponibile,
    nome_articolo,
    sezioni_report,
    sezioni_testo,
    spezza_messaggi_strutturati,
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
            'aams': '1', 'descrizione': 'MARLBORO GOLD DA 20 A.', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 0, 'media': 3.2, 'stato': ESAURITO, 'immancabile': True,
            'giorni_fine': 0, 'data_fine': None, 'mancanti_alla_data': 13,
        },
        {
            'aams': '2', 'descrizione': 'CAMEL BLUE DA 20', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 4, 'media': 1.8, 'stato': PRIMA_CONSEGNA, 'immancabile': True,
            'giorni_fine': 2, 'data_fine': '2026-11-21', 'mancanti_alla_data': 3,
        },
        {
            'aams': '7', 'descrizione': 'VEEV ONE STRAWBERRY 1.8%', 'famiglia': 'Dispositivi', 'tipo': 'dispositivo',
            'giacenza': -2, 'media': 0.6, 'stato': ESAURITO, 'immancabile': False,
            'giorni_fine': 0, 'data_fine': None, 'mancanti_alla_data': 3,
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
            'aams': '6', 'descrizione': 'DEBOLE', 'famiglia': 'Sigarette', 'tipo': 'tabacco',
            'giacenza': 1, 'media': 0.4, 'stato': PRIMA_CONSEGNA, 'immancabile': False,
            'giorni_fine': 1, 'data_fine': '2026-11-20', 'mancanti_alla_data': 2,
        },
    ]


class SezioniReportTests(TestCase):
    def test_tre_sezioni_e_api_compat(self):
        esaurite, in_esa, altre = sezioni_testo({'righe': _righe_esempio()})
        self.assertEqual([r['aams'] for r in esaurite], ['1'])
        self.assertEqual([r['aams'] for r in in_esa], ['2'])
        # Sigarette prima di Dispositivi; dentro Sigarette per data_fine
        self.assertEqual([r['aams'] for r in altre], ['6', '3', '7'])

        imm, prima = sezioni_report({'righe': _righe_esempio()})
        self.assertEqual([r['aams'] for r in imm], ['1', '2'])
        self.assertEqual([r['aams'] for r in prima], ['6', '3', '7'])
        self.assertTrue(all(r['media'] > 0 for r in imm + prima))


class FormattazioneReportTests(TestCase):
    def test_nome_e_giacenza(self):
        self.assertEqual(nome_articolo('BLENDS SILVER CLASSICS DA 20 A.'), 'Blends Silver Classics')
        self.assertEqual(nome_articolo('CAMEL BLUE DA 20'), 'Camel Blue')
        self.assertEqual(nome_articolo('201 CHESTERFIELD BLUE', aams='201'), 'Chesterfield Blue')
        self.assertEqual(nome_articolo('PLN99 VEEV ONE STRAWBERRY 1.8%'), 'Veev One Strawberry 1.8%')
        lungo = nome_articolo('ABCDEFGHIJKLMNOPQRSTUVWXYZ EXTRA LUNGO')
        self.assertLessEqual(len(lungo), 32)
        self.assertEqual(giacenza_mostrata(-4), 0)
        self.assertEqual(giacenza_mostrata(15.0), 15)

    def test_data_corta_e_relativa(self):
        oggi = date(2026, 11, 20)  # ven
        self.assertEqual(formatta_data_corta(oggi), 'ven 20/11')
        self.assertEqual(formatta_giorno_relativo(date(2026, 11, 21), oggi), 'sab')
        self.assertEqual(formatta_giorno_relativo(date(2026, 12, 5), oggi), '05/12')
        self.assertEqual(escape_html('A <B> & C'), 'A &lt;B&gt; &amp; C')

    def test_testo_nuovo_formato(self):
        oggi = date(2026, 11, 20)
        lunedi = date(2026, 11, 23)
        consegna = date(2026, 11, 23)
        esaurite, in_esa, altre = sezioni_testo({'righe': _righe_esempio()})
        testo = costruisci_testo(
            oggi=oggi, lunedi=lunedi, consegna=consegna,
            letto_alle='2026-11-20T10:02:00',
            esaurite=esaurite, in_esaurimento=in_esa, altre=altre,
        )
        self.assertIn('📦 <b>Giacenze – ven 20/11</b> · letti alle 10:02', testo)
        self.assertIn('Consegna: <b>lun 23/11</b>', testo)
        self.assertIn('🔴 <b>1 esaurita</b>', testo)
        self.assertIn('🟠 <b>1</b> finiscono entro la consegna', testo)
        self.assertIn('🟡 <b>3</b> altre prima di lunedì', testo)
        self.assertIn('🔴 <b>ESAURITE – IMMANCABILI</b>', testo)
        self.assertIn('🟠 <b>IMMANCABILI IN ESAURIMENTO</b>', testo)
        self.assertIn('🟡 <b>ALTRE PRIMA DI LUNEDÌ</b>', testo)
        self.assertIn('<b>Sigarette</b>', testo)
        self.assertIn('<b>Dispositivi</b>', testo)
        self.assertIn('• Marlboro Gold', testo)
        self.assertIn('3,2/gg · <b>−13 pz</b> a lun', testo)
        self.assertIn('giac 4 · 1,8/gg · finisce <b>sab</b>', testo)
        self.assertIn('<b>ESAURITO</b> · 0,6/gg · <b>−3 pz</b>', testo)
        self.assertNotIn('dati chiusura', testo)
        self.assertNotIn('FERMO', testo)
        self.assertNotIn('Okay', testo)

        vuoto = costruisci_testo(
            oggi=oggi, consegna=consegna, letto_alle='',
            esaurite=[], in_esaurimento=[], altre=[],
        )
        self.assertIn('✅ Nessun articolo in esaurimento fino a lunedì', vuoto)
        self.assertNotIn('ESAURITE', vuoto)

    def test_sezioni_vuote_omesse(self):
        oggi = date(2026, 11, 20)
        solo_altre = [r for r in _righe_esempio() if r['aams'] == '7']
        testo = costruisci_testo(
            oggi=oggi, consegna=date(2026, 11, 23), letto_alle='',
            esaurite=[], in_esaurimento=[], altre=solo_altre,
        )
        self.assertNotIn('ESAURITE – IMMANCABILI', testo)
        self.assertNotIn('IMMANCABILI IN ESAURIMENTO', testo)
        self.assertIn('ALTRE PRIMA DI LUNEDÌ', testo)
        self.assertIn('🟡 <b>1</b> altre prima di lunedì', testo)
        self.assertNotIn('esaurit', testo.lower().split('altre')[0])  # no 🔴 esaurite nel riepilogo

    def test_spezza_tra_articoli_con_ripetizione_sezione(self):
        oggi = date(2026, 11, 20)
        righe = []
        for i in range(12):
            righe.append({
                'aams': str(i),
                'descrizione': f'PRODOTTO LUNGO NUMERO {i} EXTRA',
                'famiglia': 'Sigarette',
                'tipo': 'tabacco',
                'giacenza': 0,
                'media': 2.0,
                'stato': ESAURITO,
                'immancabile': True,
                'giorni_fine': 0,
                'data_fine': None,
                'mancanti_alla_data': 5 + i,
            })
        header, sezioni = _parti_report(
            oggi=oggi, consegna=date(2026, 11, 23), letto_alle='',
            esaurite=righe, in_esaurimento=[], altre=[],
        )
        # Forza split stretto
        pezzi = spezza_messaggi_strutturati(header, sezioni, max_len=280)
        self.assertGreater(len(pezzi), 1)
        self.assertIn('📦 <b>Giacenze', pezzi[0])
        for pezzo in pezzi[1:]:
            self.assertIn('ESAURITE – IMMANCABILI', pezzo)
            self.assertIn('<b>Sigarette</b>', pezzo)
            self.assertLessEqual(len(pezzo), 280)
        # Nessun articolo spezzato a metà: ogni blocco ha "• " e la riga dettaglio
        for pezzo in pezzi:
            linee = pezzo.split('\n')
            for i, linea in enumerate(linee):
                if linea.startswith('• '):
                    self.assertLess(i + 1, len(linee))
                    self.assertTrue(linee[i + 1].startswith('   '))

    def test_blocco_articolo_negativo(self):
        riga = {
            'descrizione': 'TEST', 'aams': '9', 'giacenza': -3, 'media': 1.1,
            'mancanti_alla_data': 4, 'data_fine': '2026-11-21',
        }
        blocco = blocco_articolo(riga, stile='in_esaurimento', oggi=date(2026, 11, 20))
        self.assertIn('giac 0', blocco)
        self.assertNotIn('giac -', blocco)

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
            'letto_alle': '2026-11-20T09:30:00',
            'articoli': [
                {
                    'aams': 'E1', 'descrizione': 'ESAURITO HOT DA 20 A.', 'categoria': 'SIGARETTE',
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
        self.assertEqual(body['lunedi'], '2026-11-23')
        self.assertTrue(any(r['aams'] == 'E1' for r in body['immancabili']))
        self.assertFalse(any(r['aams'] == 'F0' for r in body['immancabili'] + body['prima_di_lunedi']))
        self.assertIn('messaggi', body)
        self.assertEqual(body['messaggi'][0], body['testo'])
        self.assertIn('• Esaurito Hot', body['testo'])
        self.assertIn('ESAURITE – IMMANCABILI', body['testo'])


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
            'letto_alle': '2026-11-20T10:00:00',
            'articoli': [{
                'aams': '201', 'descrizione': 'CHESTERFIELD <GOLD> DA 20 A.', 'categoria': 'SIGARETTE',
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
        self.assertIn('Chesterfield &lt;Gold&gt;', data['testo'])
        self.assertIn('ESAURITE – IMMANCABILI', data['testo'])
