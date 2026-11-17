import json
import socket
import urllib.error
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from reconciliation.gratta_preordine import (
    calcola_righe,
    giorni_alla_consegna,
    media_riferimento,
    proposta_pacchi,
)

# Medie e giacenze della chiusura del 16/11/2026. Consegna 18/11, un giorno di vendita prima.
CONTROLLO = [
    ('3101', 'NUMERI FORTUNATI NEW', '11.55', 50, '150', 54),
    ('3127', 'MILIARDARIO NEW', '10.6', 60, '300', 119),
    ('3116', '50X NEW', '7.76', 30, '300', 27),
    ('3121', 'FAI SCOPA BONUS', '10.65', 75, '150', 97),
    ('3058', 'CRUCIJOLLY', '9.1', 50, '150', 40),
    ('3072', 'NEW TUTTO PER TUTTO', '3.51', 60, '300', 26),
    ('3325', 'NUMERISSIMI', '13.1', 60, '300', 112),
    ('3113', "BUONDI'", '4.6', 150, '150', 91),
    ('3081', 'DOPPIA SFIDA CLASSIC', '4.23', 60, '300', 43),
    ('3115', '20X NEW', '3.29', 60, '300', 18),
    ('3080', 'DOPPIA SFIDA SMALL', '3.95', 50, '150', 9),
    ('3124', 'GIOCHI DI NATALE SUPER', '1.84', 30, '300', 58),
    ('3088', 'IL TURISTA PER SEMPRE', '2.56', 60, '300', 44),
    ('3099', 'MEGA MILIARDARIO NEW', '3.56', 30, '300', 38),
    ('3125', 'GIOCHI DI NATALE EXTRA', '3.32', 15, '300', 36),
    ('3323', 'COLOR PUZZLE 10€', '1.21', 30, '300', 2),
    ('3082', 'DOPPIA SFIDA SUPER', '1.21', 30, '300', 14),
    ('3322', 'COLOR PUZZLE 5€', '1.23', 60, '300', 39),
    ('3126', 'MAXI MILIARDARIO NEW', '1.79', 15, '300', 60),
    ('3114', 'SUPER NUMERISSIMI', '1.56', 30, '300', 39),
    ('3324', 'DUAL PLAY', '0.51', 60, '300', 45),
    ('5037', 'LOTTERIA ITALIA 2026', '0.84', 20, '100', 73),
    ('3123', 'GIOCHI DI NATALE', '8.93', 60, '300', 114),
    ('3118', "VIVA L'ESTATE MINI", '1.23', 75, '150', 68),
    ('3320', 'ULTRA NUMERISSIMI', '0.74', 15, '300', 33),
    ('3110', 'MILIONI DI DIAMANTI', '0.49', 10, '300', 18),
    ('3117', '100X NEW', '0.33', 15, '300', 26),
    ('3093', 'NEW EXTRA TUTTO PER TUTTO', '0.16', 15, '300', 40),
    ('3112', 'CASINÒ RICCO', '0.65', 30, '300', 22),
    ('3120', "VIVA L'ESTATE SUPER", '0.4', 30, '300', 18),
]


def _ordinati(giorni):
    trovati = {}
    totale = Decimal('0')
    for codice, nome, media, biglietti, valore, giacenza in CONTROLLO:
        proposta = proposta_pacchi(media, giacenza, biglietti, giorni, 1)
        if proposta['pacchi']:
            trovati[nome] = proposta['pacchi']
            totale += proposta['pacchi'] * Decimal(valore)
    return trovati, totale


class FormulaGrattaTests(TestCase):
    def test_un_giorno_prima_della_consegna(self):
        self.assertEqual(
            giorni_alla_consegna(date(2026, 11, 17), date(2026, 11, 16), date(2026, 11, 18)),
            1,
        )

    def test_cinque_giorni(self):
        trovati, totale = _ordinati(5)
        self.assertEqual(trovati, {
            '50X NEW': 1,
            'CRUCIJOLLY': 1,
            'DOPPIA SFIDA SMALL': 1,
            'NUMERI FORTUNATI NEW': 1,
        })
        self.assertEqual(totale, Decimal('750'))

    def test_sette_giorni(self):
        trovati, totale = _ordinati(7)
        self.assertEqual(trovati, {
            'COLOR PUZZLE 10€': 1,
            '50X NEW': 2,
            'CRUCIJOLLY': 1,
            'DOPPIA SFIDA SMALL': 1,
            'NUMERI FORTUNATI NEW': 1,
        })
        self.assertEqual(totale, Decimal('1350'))

    def test_nove_giorni(self):
        trovati, totale = _ordinati(9)
        self.assertEqual(trovati, {
            'COLOR PUZZLE 10€': 1,
            '50X NEW': 2,
            'NUMERISSIMI': 1,
            'CRUCIJOLLY': 2,
            'DOPPIA SFIDA SMALL': 1,
            'NUMERI FORTUNATI NEW': 2,
        })
        self.assertEqual(totale, Decimal('1950'))

    def test_media_esclude_i_giorni_esauriti_e_pesa_3_2_1(self):
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
        media, esclusi = media_riferimento(vendite, giacenze, aperture, ultimo, 60)
        self.assertEqual(esclusi, 1)
        self.assertEqual(media, Decimal('28') / Decimal('6'))

    def test_gioco_escluso_resta_a_zero_pacchi(self):
        ultimo = date(2026, 11, 16)
        dati = {
            'ultimo_giorno_chiuso': ultimo.isoformat(),
            'giorni_apertura': [ultimo.isoformat()],
            'giochi': [{
                'id_articolo': 'x',
                'codice': '3050',
                'descrizione': 'FAI SCOPA NEW',
                'prezzo': 2,
                'biglietti_pacco': 10,
                'valore_pacco': 20,
                'giacenza': 0,
                'vendite_giornaliere': {ultimo.isoformat(): 10},
                'giacenze_fine_giorno': {},
            }],
        }
        righe = calcola_righe(dati, date(2026, 11, 17), giorni_copertura=7, data_consegna=date(2026, 11, 18))
        self.assertEqual(righe[0]['pacchi'], 0)
        self.assertTrue(righe[0]['escluso'])


class GrattaApiTests(TestCase):
    def setUp(self):
        from reconciliation.models import Company, TabaUnoRequest
        self.company = Company.objects.create(denominazione='Tabacchi Demo')
        self.user = User.objects.create_user('daniele', password='secret', is_staff=True)
        self.client.login(username='daniele', password='secret')
        session = self.client.session
        session['active_company_id'] = self.company.id
        session.save()
        self.TabaUnoRequest = TabaUnoRequest

    def _lettura(self, giochi):
        return self.TabaUnoRequest.objects.create(
            company=self.company,
            date=date(2026, 11, 17),
            tipo='preordine_gratta',
            status='done',
            payload={
                'ultimo_giorno_chiuso': '2026-11-16',
                'letto_alle': '2026-11-17T09:52:00+01:00',
                'giorni_apertura': ['2026-11-16'],
                'giochi': giochi,
            },
        )

    def _gioco(self, codice='3116', giacenza=0, media_vendite=40):
        return {
            'id_articolo': f'id-{codice}',
            'codice': codice,
            'descrizione': '50X NEW',
            'prezzo': 10,
            'biglietti_pacco': 30,
            'valore_pacco': 300,
            'giacenza': giacenza,
            'vendite_giornaliere': {'2026-11-16': media_vendite},
            'giacenze_fine_giorno': {},
        }

    def test_crea_richiesta_e_preordine(self):
        creato = self.client.post('/api/gratta/preordini/', data='{}', content_type='application/json')
        self.assertEqual(creato.status_code, 201)
        request_id = creato.json()['id']
        di_nuovo = self.client.post('/api/gratta/preordini/', data='{}', content_type='application/json')
        self.assertEqual(di_nuovo.status_code, 200)
        self.assertEqual(di_nuovo.json()['id'], request_id)
        self.TabaUnoRequest.objects.filter(id=request_id).update(
            status='done',
            payload={
                'ultimo_giorno_chiuso': '2026-11-16',
                'letto_alle': '2026-11-17T09:52:00+01:00',
                'giorni_apertura': ['2026-11-16'],
                'giochi': [self._gioco()],
            },
        )
        pronto = self.client.post(
            f'/api/gratta/preordini/da-richiesta/{request_id}/',
            data=json.dumps({'giorni_copertura': 7, 'data_consegna': '2026-11-18'}),
            content_type='application/json',
        )
        self.assertEqual(pronto.status_code, 201)
        self.assertEqual(pronto.json()['preordine']['stato'], 'bozza')
        self.assertEqual(pronto.json()['preordine']['righe'][0]['codice'], '3116')

    def test_elimina_ordine_e_consente_una_nuova_lettura(self):
        lettura = self._lettura([self._gioco()])
        creato = self.client.post(
            f'/api/gratta/preordini/da-richiesta/{lettura.id}/',
            data=json.dumps({'giorni_copertura': 7, 'data_consegna': '2026-11-18'}),
            content_type='application/json',
        )
        preordine_id = creato.json()['preordine']['id']
        eliminato = self.client.delete(f'/api/gratta/preordini/{preordine_id}/')
        self.assertEqual(eliminato.status_code, 200)
        self.assertEqual(self.client.get(f'/api/gratta/preordini/{preordine_id}/').status_code, 404)
        nuova = self.client.post('/api/gratta/preordini/', data='{}', content_type='application/json')
        self.assertEqual(nuova.status_code, 201)
        self.assertNotEqual(nuova.json()['id'], lettura.id)

    def test_patch_conserva_la_correzione_manuale(self):
        lettura = self._lettura([self._gioco('3116', giacenza=0), self._gioco('3058', giacenza=0)])
        creato = self.client.post(
            f'/api/gratta/preordini/da-richiesta/{lettura.id}/',
            data=json.dumps({'giorni_copertura': 7, 'data_consegna': '2026-11-18'}),
            content_type='application/json',
        )
        preordine = creato.json()['preordine']
        proposti = {riga['codice']: riga['pacchi_proposti'] for riga in preordine['righe']}
        patch = self.client.patch(
            f"/api/gratta/preordini/{preordine['id']}/",
            data=json.dumps({
                'giorni_copertura': 5,
                'righe': [{'codice': '3116', 'pacchi': 4}],
            }),
            content_type='application/json',
        )
        self.assertEqual(patch.status_code, 200)
        righe = {riga['codice']: riga for riga in patch.json()['preordine']['righe']}
        self.assertEqual(righe['3116']['pacchi'], 4)
        self.assertTrue(righe['3116']['corretto_a_mano'])
        self.assertEqual(righe['3058']['pacchi'], righe['3058']['pacchi_proposti'])
        self.assertNotEqual(righe['3058']['pacchi_proposti'], proposti['3058'])
        ancora = self.client.patch(
            f"/api/gratta/preordini/{preordine['id']}/",
            data=json.dumps({'giorni_copertura': 9}),
            content_type='application/json',
        )
        righe = {riga['codice']: riga for riga in ancora.json()['preordine']['righe']}
        self.assertEqual(righe['3116']['pacchi'], 4)
        self.assertEqual(righe['3058']['pacchi'], righe['3058']['pacchi_proposti'])

    def _preordine_sopra_minimo(self):
        lettura = self._lettura([self._gioco(giacenza=0, media_vendite=80)])
        return self.client.post(
            f'/api/gratta/preordini/da-richiesta/{lettura.id}/',
            data=json.dumps({'giorni_copertura': 9, 'data_consegna': '2026-11-18'}),
            content_type='application/json',
        ).json()['preordine']

    def test_invio_bloccato_sotto_i_900(self):
        lettura = self._lettura([self._gioco(giacenza=1000, media_vendite=0)])
        preordine = self.client.post(
            f'/api/gratta/preordini/da-richiesta/{lettura.id}/',
            data=json.dumps({'giorni_copertura': 7, 'data_consegna': '2026-11-18'}),
            content_type='application/json',
        ).json()['preordine']
        self.assertEqual(preordine['totale'], 0)
        response = self.client.post(f"/api/gratta/preordini/{preordine['id']}/invia/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue('900' in response.json()['error'] or response.json()['error'].startswith('Nessun'))

    def test_invio_successo_errore_e_timeout(self):
        preordine = self._preordine_sopra_minimo()
        self.assertGreaterEqual(preordine['totale'], 900)

        class Ok:
            def read(self):
                return b'{}'

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.dict('os.environ', {'N8N_GRATTA_WEBHOOK_URL': 'http://n8n.test/hook', 'N8N_GRATTA_TOKEN': 'segreto'}), \
                patch('reconciliation.gratta_views.urllib.request.urlopen', return_value=Ok()):
            ok = self.client.post(f"/api/gratta/preordini/{preordine['id']}/invia/")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['preordine']['stato'], 'inviato_n8n')
        self.assertNotIn('segreto', json.dumps(ok.json()))

        from reconciliation.models import GrattaPreordine
        GrattaPreordine.objects.filter(id=preordine['id']).update(stato='bozza', callback_token_hash='')
        errore = urllib.error.HTTPError('http://n8n.test/hook', 500, 'err', hdrs=None, fp=BytesIO(b'boom'))
        with patch.dict('os.environ', {'N8N_GRATTA_WEBHOOK_URL': 'http://n8n.test/hook', 'N8N_GRATTA_TOKEN': 'segreto'}), \
                patch('reconciliation.gratta_views.urllib.request.urlopen', side_effect=errore):
            fallito = self.client.post(f"/api/gratta/preordini/{preordine['id']}/invia/")
        self.assertEqual(fallito.status_code, 502)
        self.assertEqual(fallito.json()['preordine']['stato'], 'errore')

        timeout = urllib.error.URLError(socket.timeout('timed out'))
        with patch.dict('os.environ', {'N8N_GRATTA_WEBHOOK_URL': 'http://n8n.test/hook', 'N8N_GRATTA_TOKEN': 'segreto'}), \
                patch('reconciliation.gratta_views.urllib.request.urlopen', side_effect=timeout):
            lento = self.client.post(f"/api/gratta/preordini/{preordine['id']}/invia/")
        self.assertEqual(lento.status_code, 504)
        self.assertIn('15', lento.json()['error'])

    def test_callback_token_e_transizioni(self):
        preordine = self._preordine_sopra_minimo()
        chiaro = 'token-callback'

        class Ok:
            def read(self):
                return b''

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        with patch.dict('os.environ', {'N8N_GRATTA_WEBHOOK_URL': 'http://n8n.test/hook', 'N8N_GRATTA_TOKEN': 'segreto'}), \
                patch('reconciliation.gratta_views.secrets.token_urlsafe', return_value=chiaro), \
                patch('reconciliation.gratta_views.urllib.request.urlopen', return_value=Ok()):
            self.client.post(f"/api/gratta/preordini/{preordine['id']}/invia/")
        sbagliato = self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'carrello_pronto', 'messaggio': 'no'}),
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer altro',
        )
        self.assertEqual(sbagliato.status_code, 401)
        pronto = self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'carrello_pronto', 'messaggio': 'Carrello pronto', 'totale_portale': 1350}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chiaro}',
        )
        self.assertEqual(pronto.status_code, 200)
        self.assertEqual(pronto.json()['stato'], 'carrello_pronto')
        indietro = self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'bozza'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chiaro}',
        )
        self.assertEqual(indietro.status_code, 409)
        self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'confermato', 'messaggio': 'ok'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chiaro}',
        )
        self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'inviato_portale', 'messaggio': 'fatto'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chiaro}',
        )
        regresso = self.client.post(
            f"/api/gratta/preordini/{preordine['id']}/stato/",
            data=json.dumps({'stato': 'carrello_pronto'}),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Bearer {chiaro}',
        )
        self.assertEqual(regresso.status_code, 409)

    def test_json_di_prova_non_contiene_il_token(self):
        preordine = self._preordine_sopra_minimo()
        response = self.client.get(f"/api/gratta/preordini/{preordine['id']}/json/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('token', response.json()['callback'])
        self.assertGreater(response.json()['totale']['importo'], 0)
