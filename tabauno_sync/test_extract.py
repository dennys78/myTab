import sqlite3
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tabauno_sync.extract import _collect_payments, extract_closure

DAY = '2026-11-16'

SETTORI = [
    ('01', 'TABACCHI'),
    ('02', 'CAFFE'),
    ('03', 'PASTICCERIA'),
    ('04', 'BIBITE'),
    ('06', 'BIRRE'),
    ('09', 'ROSTICCERIA'),
    ('10', 'PASTIGLIAGGI'),
    ('14', 'CARTINE E ACC.'),
    ('15', 'VALORI BOLLATI'),
    ('20', 'SIGARETTE ELETTRONICHE'),
    ('90', 'GRATTA E VINCI'),
]

SALES = [
    ('01', 1582.70),
    ('02', 54.60),
    ('03', 8.10),
    ('04', 8.00),
    ('06', 15.00),
    ('09', 16.00),
    ('10', 12.90),
    ('14', 16.90),
    ('15', 79.00),
    ('20', 94.40),
    ('90', 465.00),
]


def _build_db(path, *, include_live=True):
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE settori (CodiceSettore TEXT, Descrizione TEXT);
        CREATE TABLE MovimentiCassa (CodiceMovimentoCassa TEXT, DescrizioneMovimento TEXT);
        CREATE TABLE cassaglobal (
            Data TEXT, CodiceSettore TEXT, Descrizione TEXT, Importo REAL, RagioneSociale TEXT
        );
        CREATE TABLE conto (Data TEXT, Incassi REAL, Pos REAL, Contanti REAL);
    """)
    connection.executemany('INSERT INTO settori VALUES (?, ?)', SETTORI)
    connection.execute("INSERT INTO MovimentiCassa VALUES ('95', 'PAG.FORNITORI')")
    connection.execute(
        "INSERT INTO conto VALUES (?, 2855.80, 699.70, 2156.10)",
        (DAY,),
    )
    if include_live:
        rows = [(DAY, code, name, amount, '') for code, amount in SALES for name in [dict(SETTORI)[code]]]
        rows.append((DAY, '301', 'INCASSO LOTTO/10&LOTTO', 453.00, 'LOTTOMATICA'))
        rows.append((DAY, '302', 'VINCITE LOTTO/10&LOTTO', -162.50, 'LOTTOMATICA'))
        rows.append((DAY, '300', 'VINCITE GRATTA E VINCI', -237.00, 'LOTTOMATICA'))
        rows.append((DAY, '410', 'INCASSO MOONEY', 447.90, 'MOONEY'))
        rows.append((DAY, '600', 'INCASSO SISAL', 49.00, 'SISAL'))
        rows.append((DAY, '601', 'VINCITE SISAL', -10.20, 'SISAL'))
        rows.append((DAY, '95', 'PAGAMENTO FORNITORE', -37.00, ''))
        connection.executemany(
            'INSERT INTO cassaglobal (Data, CodiceSettore, Descrizione, Importo, RagioneSociale) VALUES (?, ?, ?, ?, ?)',
            rows,
        )
    connection.commit()
    connection.close()


def _add_payments(path, rows):
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS StoricoCassa (
            Data TEXT, Importo REAL, TipoPagamento TEXT, Ora_Chiusura TEXT
        )
    """)
    connection.executemany(
        'INSERT INTO StoricoCassa (Data, Importo, TipoPagamento, Ora_Chiusura) VALUES (?, ?, ?, ?)',
        rows,
    )
    connection.commit()
    connection.close()


def _voce(payload, description):
    matches = [item for item in payload['voci'] if item['descrizione'] == description]
    if len(matches) != 1:
        raise AssertionError(f'{description}: {matches}')
    return matches[0]


class ExtractClosureTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / 'TabaUno.db'
        _build_db(self.db)

    def tearDown(self):
        self.directory.cleanup()

    def test_rule_a_matches_control_day(self):
        payload = extract_closure(self.db, DAY, gratta='A', snapshot=True)
        gratta = _voce(payload, 'GRATTA E VINCI')
        lotto = _voce(payload, 'LOTTOMATICA')
        self.assertEqual((gratta['entrate'], gratta['uscite'], gratta['saldo']), (465.0, 0.0, 465.0))
        self.assertEqual((lotto['entrate'], lotto['uscite'], lotto['saldo']), (453.0, 399.5, 53.5))
        self.assertEqual(payload['totale'], {'entrate': 3302.5, 'uscite': 446.7, 'saldo': 2855.8})
        self.assertEqual(payload['incasso'], {'pos': 699.7, 'contanti': 2156.1, 'totale': 2855.8})
        self.assertTrue(payload['verifiche']['saldo_uguale_incasso'])
        self.assertTrue(payload['verifiche']['pos_piu_contanti_ok'])
        self.assertTrue(payload['verifiche']['saldo_uguale_movimenti'])
        self.assertEqual(payload['verifiche']['codici_sconosciuti'], [])
        self.assertEqual(_voce(payload, 'PAG.FORNITORI')['saldo'], -37.0)
        self.assertEqual(_voce(payload, 'TABACCHI')['reparto'], '01')
        self.assertEqual(lotto['reparto'], '97')
        self.assertLess(
            payload['voci'].index(gratta),
            payload['voci'].index(lotto),
        )

    def test_rule_b_moves_gratta_winnings(self):
        payload = extract_closure(self.db, DAY, gratta='B', snapshot=False)
        gratta = _voce(payload, 'GRATTA E VINCI')
        lotto = _voce(payload, 'LOTTOMATICA')
        self.assertEqual((gratta['entrate'], gratta['uscite'], gratta['saldo']), (465.0, 237.0, 228.0))
        self.assertEqual((lotto['entrate'], lotto['uscite'], lotto['saldo']), (453.0, 162.5, 290.5))
        self.assertEqual(payload['totale']['saldo'], 2855.8)
        self.assertEqual(
            Decimal(str(payload['incasso']['pos'])) + Decimal(str(payload['incasso']['contanti'])),
            Decimal('2855.80'),
        )

    def test_empty_day_is_flagged(self):
        payload = extract_closure(self.db, '2020-01-01', gratta='B', snapshot=False)
        self.assertEqual(payload['voci'], [])
        self.assertTrue(payload['verifiche']['senza_righe'])
        self.assertFalse(payload['verifiche']['saldo_uguale_incasso'])

    def test_storico_when_live_has_no_rows(self):
        live = Path(self.directory.name) / 'vuoto.db'
        _build_db(live, include_live=False)
        payload = extract_closure(live, DAY, storico_path=self.db, gratta='A', snapshot=False)
        self.assertEqual(payload['verifiche']['sorgente'], 'CassaGlobal')
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 1582.7)

    def test_missing_conto_marks_closure_not_done(self):
        bare = Path(self.directory.name) / 'senza_conto.db'
        connection = sqlite3.connect(bare)
        connection.executescript("""
            CREATE TABLE settori (CodiceSettore TEXT, Descrizione TEXT);
            CREATE TABLE MovimentiCassa (CodiceMovimentoCassa TEXT, DescrizioneMovimento TEXT);
            CREATE TABLE cassaglobal (
                Data TEXT, CodiceSettore TEXT, Descrizione TEXT, Importo REAL, RagioneSociale TEXT
            );
            CREATE TABLE conto (Data TEXT, Incassi REAL, Pos REAL, Contanti REAL);
        """)
        connection.execute("INSERT INTO settori VALUES ('01', 'TABACCHI')")
        connection.execute(
            "INSERT INTO cassaglobal VALUES ('2020-01-02', '01', 'TABACCHI', 10, '')"
        )
        connection.commit()
        connection.close()
        payload = extract_closure(bare, '2020-01-02', gratta='B', snapshot=False)
        self.assertFalse(payload['verifiche']['chiusura_eseguita'])
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 10.0)

    def test_today_reads_payments_not_storico_voci(self):
        today = date.today().isoformat()
        storico = Path(self.directory.name) / 'storico_oggi.db'
        _build_db(storico)
        connection = sqlite3.connect(storico)
        connection.execute(
            "INSERT INTO cassaglobal (Data, CodiceSettore, Descrizione, Importo, RagioneSociale) VALUES (?, '01', 'TABACCHI', 12, '')",
            (today,),
        )
        connection.commit()
        connection.close()
        _add_payments(storico, [(today, 5.0, 'Pagamento elettronico', '20:23:48')])
        live = sqlite3.connect(self.db)
        live.execute(
            "INSERT INTO cassaglobal (Data, CodiceSettore, Descrizione, Importo, RagioneSociale) VALUES (?, '01', 'TABACCHI', 5, '')",
            (today,),
        )
        live.execute('INSERT INTO conto VALUES (?, 5, 5, 0)', (today,))
        live.commit()
        live.close()
        payload = extract_closure(self.db, today, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(payload['verifiche']['sorgente'], 'cassaglobal')
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 5.0)
        self.assertEqual(payload['pagamenti']['pag_pos'], 5.0)
        self.assertEqual(payload['pagamenti']['ora_chiusura'], '20:23:48')
        self.assertTrue(payload['verifiche']['chiusura_eseguita'])
        self.assertEqual(payload['verifiche']['messaggio'], '')

    def test_payments_match_control_day(self):
        storico = Path(self.directory.name) / 'storico_pagamenti.db'
        _add_payments(storico, [
            (DAY, 699.70, 'Pagamento elettronico', '20:23:48'),
            (DAY, 1000.10, 'Pagamento cassa auto', '20:23:48'),
            (DAY, 1156.00, 'Pagamento cassa auto', '20:23:48'),
        ])
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(payload['totale'], {'entrate': 3302.5, 'uscite': 446.7, 'saldo': 2855.8})
        self.assertEqual(payload['pagamenti'], {
            'contanti': 0.0,
            'pag_pos': 699.7,
            'cassa_auto': 2156.1,
            'reso_cont': 0.0,
            'reso_auto': 0.0,
            'distrib': 0.0,
            'non_classificato': 0.0,
            'totale': 2855.8,
            'ora_chiusura': '20:23:48',
        })
        self.assertTrue(payload['verifiche']['pagamenti_uguale_saldo'])
        self.assertTrue(payload['verifiche']['pagamenti_uguale_conto'])
        self.assertTrue(payload['verifiche']['chiusura_eseguita'])
        self.assertEqual(payload['verifiche']['tipi_pagamento_sconosciuti'], [])

    def test_unknown_payment_types_are_kept(self):
        storico = Path(self.directory.name) / 'storico_tipi.db'
        _add_payments(storico, [
            (DAY, 10, '  PAGAMENTO CONTANTE ', '18:00:00'),
            (DAY, 531.40, 'Cassa', '18:00:00'),
            (DAY, -2.50, 'RESO CASSA AUTO', '18:00:01'),
            (DAY, 3, 'Buono pasto', '18:00:01'),
            (DAY, 1, None, '18:00:01'),
        ])
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        pagamenti = payload['pagamenti']
        self.assertEqual(pagamenti['contanti'], 10.0)
        self.assertEqual(pagamenti['distrib'], 531.4)
        self.assertEqual(pagamenti['reso_auto'], -2.5)
        self.assertEqual(pagamenti['reso_cont'], 0.0)
        self.assertEqual(pagamenti['non_classificato'], 4.0)
        self.assertEqual(pagamenti['ora_chiusura'], '18:00:01')
        self.assertEqual(payload['verifiche']['tipi_pagamento_sconosciuti'], ['(vuoto)', 'Buono pasto'])
        self.assertFalse(payload['verifiche']['pagamenti_uguale_conto'])

    def test_closure_needs_conto_and_payment_rows(self):
        storico = Path(self.directory.name) / 'storico_vuoto.db'
        _add_payments(storico, [])
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        self.assertFalse(payload['verifiche']['chiusura_eseguita'])
        self.assertEqual(payload['pagamenti']['totale'], 0.0)
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 1582.7)

    def test_closed_receipt_drops_sales_after_closure(self):
        storico = Path(self.directory.name) / 'storico_scontrino.db'
        connection = sqlite3.connect(storico)
        connection.execute("""
            CREATE TABLE StoricoCassa (
                Data TEXT, CodiceSettore TEXT, Descrizione TEXT, Importo REAL,
                RagioneSociale TEXT, TipoPagamento TEXT, Ora_Chiusura TEXT
            )
        """)
        connection.executemany(
            '''INSERT INTO StoricoCassa
               (Data, CodiceSettore, Descrizione, Importo, RagioneSociale, TipoPagamento, Ora_Chiusura)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            [
                (DAY, '01', 'CHESTERFIELD', 1000.00, '', 'Pagamento cassa auto', '20:23:40'),
                (DAY, '01', 'PHILIP MORRIS', 694.90, '', 'Pagamento cassa auto', '20:23:40'),
                (DAY, '02', 'CAFFE', 54.60, '', 'Pagamento cassa auto', '20:23:40'),
                (DAY, '301', 'INCASSO LOTTO/10&LOTTO', 453.00, '', 'Pagamento cassa auto', '20:23:40'),
                (DAY, '302', 'VINCITE LOTTO/10&LOTTO', -162.50, '', 'Pagamento cassa auto', '20:23:40'),
                (DAY, '300', 'VINCITE GRATTA E VINCI', -237.00, '', 'Pagamento cassa auto', '20:23:40'),
            ],
        )
        connection.commit()
        connection.close()
        live = sqlite3.connect(self.db)
        live.execute(
            "UPDATE cassaglobal SET Importo = 1706.50 WHERE Data = ? AND CodiceSettore = '01'",
            (DAY,),
        )
        live.commit()
        live.close()
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(payload['verifiche']['sorgente'], 'StoricoCassa')
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 1694.9)
        self.assertEqual(_voce(payload, 'CAFFE')['entrate'], 54.6)
        self.assertEqual(_voce(payload, 'LOTTOMATICA')['saldo'], 290.5)

    def test_two_closures_on_the_same_day_are_summed(self):
        storico = Path(self.directory.name) / 'storico_due_chiusure.db'
        connection = sqlite3.connect(storico)
        connection.execute("""
            CREATE TABLE StoricoCassa (
                Data TEXT, CodiceSettore TEXT, Descrizione TEXT, Importo REAL,
                TipoPagamento TEXT, Ora_Chiusura TEXT
            )
        """)
        connection.executemany(
            '''INSERT INTO StoricoCassa
               (Data, CodiceSettore, Descrizione, Importo, TipoPagamento, Ora_Chiusura)
               VALUES (?, ?, ?, ?, ?, ?)''',
            [
                (DAY, '01', 'TABACCHI', 100.00, 'Pagamento cassa auto', '18:00:00'),
                (DAY, '01', 'TABACCHI', 5.80, 'Pagamento contante', '20:23:48'),
            ],
        )
        connection.commit()
        connection.close()
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 105.8)

    def test_duplicated_closure_stamp_keeps_department_total(self):
        storico = Path(self.directory.name) / 'storico_doppione.db'
        connection = sqlite3.connect(storico)
        connection.execute("""
            CREATE TABLE StoricoCassa (
                Data TEXT, CodiceSettore TEXT, Descrizione TEXT, Importo REAL,
                TipoPagamento TEXT, Ora_Chiusura TEXT
            )
        """)
        connection.executemany(
            '''INSERT INTO StoricoCassa
               (Data, CodiceSettore, Descrizione, Importo, TipoPagamento, Ora_Chiusura)
               VALUES (?, ?, ?, ?, ?, ?)''',
            [
                (DAY, '01', 'TABACCHI', 1582.70, 'Pagamento cassa auto', '08:00:00'),
                (DAY, '01', 'TABACCHI', 1582.70, 'Pagamento cassa auto', '20:00:00'),
            ],
        )
        connection.commit()
        connection.close()
        payload = extract_closure(self.db, DAY, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(payload['verifiche']['sorgente'], 'cassaglobal')
        self.assertEqual(_voce(payload, 'TABACCHI')['entrate'], 1582.7)

    def test_payment_rounding_is_half_up_on_the_total(self):
        payments = _collect_payments([
            ('Pagamento contante', Decimal('1.005'), 1, None),
            (' pagamento contante ', Decimal('1.004'), 1, None),
        ])
        self.assertEqual(payments['importi']['contanti'], Decimal('2.01'))
        self.assertEqual(payments['totale'], Decimal('2.01'))

    def test_locked_database_retries_then_reads(self):
        calls = {'n': 0}
        real = sqlite3.connect

        def flaky(target, *args, **kwargs):
            calls['n'] += 1
            if calls['n'] < 3:
                raise sqlite3.OperationalError('database is locked')
            return real(target, *args, **kwargs)

        with patch('tabauno_sync.extract.time.sleep'), patch('tabauno_sync.extract.sqlite3.connect', flaky):
            payload = extract_closure(self.db, DAY, gratta='A', snapshot=False)
        self.assertGreaterEqual(calls['n'], 3)
        self.assertEqual(payload['totale']['saldo'], 2855.8)


if __name__ == '__main__':
    unittest.main()
