import sqlite3
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from tabauno_sync.extract import extract_closure

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

    def test_today_does_not_open_storico(self):
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
        payload = extract_closure(self.db, today, storico_path=storico, gratta='B', snapshot=False)
        self.assertEqual(payload['verifiche']['sorgente'], 'cassaglobal')
        self.assertEqual(payload['voci'], [])
        self.assertFalse(payload['verifiche']['chiusura_eseguita'])
        self.assertIn('non ancora eseguita', payload['verifiche']['messaggio'])

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
