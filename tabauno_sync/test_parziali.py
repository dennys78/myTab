import sqlite3
import tempfile
import unittest
from pathlib import Path

from tabauno_sync.parziali import extract_parziali_cassa


def _db(path, script, rows=()):
    connection = sqlite3.connect(path)
    connection.executescript(script)
    for sql, values in rows:
        connection.executemany(sql, values)
    connection.commit()
    connection.close()


class ExtractParzialiTests(unittest.TestCase):
    def test_aggrega_settori_e_meta(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tabauno = Path(directory.name) / 'TabaUno.db'
        _db(tabauno, """
            CREATE TABLE cassagiorno (
                CodiceSettore TEXT, Importo REAL, Data TEXT, Ora TEXT
            );
            CREATE TABLE settori (
                CodiceSettore TEXT, Descrizione TEXT
            );
        """, [
            ('INSERT INTO settori VALUES (?, ?)', [
                ('01', 'TABACCHI'),
                ('90', 'GRATTA E VINCI'),
                ('300', 'VINCITE GRATTA'),
                ('02', 'CAFFE'),
            ]),
            ('INSERT INTO cassagiorno VALUES (?, ?, ?, ?)', [
                ('01', 100.5, '2026-11-21', '09:10'),
                ('01', 50.4, '2026-11-21', '11:05'),
                ('90', 465.0, '2026-11-21', '10:00'),
                ('300', 999.0, '2026-11-21', '10:30'),  # vincite: presenti nel payload grezzo
                ('02', 54.6, '2026-11-21', '08:00'),
            ]),
        ])
        payload = extract_parziali_cassa(tabauno)
        self.assertEqual(payload['data'], '2026-11-21')
        self.assertEqual(payload['ultima_ora'], '11:05')
        self.assertEqual(payload['righe_totali'], 5)
        by_code = {r['codice']: r for r in payload['settori']}
        self.assertEqual(by_code['01']['importo'], 150.9)
        self.assertEqual(by_code['01']['n'], 2)
        self.assertEqual(by_code['01']['descrizione'], 'TABACCHI')
        self.assertEqual(by_code['90']['importo'], 465.0)
        self.assertIn('300', by_code)  # grezzo include tutto; filtro nel backend
        self.assertTrue(payload['letto_alle'])

    def test_tabella_vuota(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        tabauno = Path(directory.name) / 'TabaUno.db'
        _db(tabauno, """
            CREATE TABLE cassagiorno (
                CodiceSettore TEXT, Importo REAL, Data TEXT, Ora TEXT
            );
        """)
        payload = extract_parziali_cassa(tabauno)
        self.assertEqual(payload['settori'], [])
        self.assertEqual(payload['righe_totali'], 0)
        self.assertEqual(payload['data'], '')
