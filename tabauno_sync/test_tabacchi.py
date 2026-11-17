import sqlite3
import tempfile
import unittest
from pathlib import Path

from tabauno_sync.tabacchi import extract_tabacchi_data


def _db(path, script, rows=()):
    connection = sqlite3.connect(path)
    connection.executescript(script)
    for sql, values in rows:
        connection.executemany(sql, values)
    connection.commit()
    connection.close()


class ExtractTabacchiTests(unittest.TestCase):
    def test_prende_id_massimo_e_vendite_settore_01(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        tabauno = root / 'TabaUno.db'
        storico = root / 'TabaUnoStorico.db'
        magx = root / 'Db_MagX.db'
        _db(tabauno, """
            CREATE TABLE tabacchi (
                ID INTEGER, CodiceAams TEXT, Descrizione TEXT, Categoria TEXT,
                Prezzo REAL, PrezzoKG REAL, MinimoOrdine REAL, Giacenza REAL
            );
        """, [
            ('INSERT INTO tabacchi VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
                (1, '201', 'CHESTERFIELD  BLUE  KS DA 20 A.', 'SIGARETTE', 5.8, 290, 200, 10),
                (9, '201', 'CHESTERFIELD BLUE KS DA 20 A.', 'SIGARETTE', 5.8, 290, 200, 96),
                (2, '999', 'SENZA VENDITE', 'SIGARETTE', 5, 250, 200, 5),
            ]),
        ])
        _db(storico, """
            CREATE TABLE StoricoCassa (
                Data TEXT, CodiceSettore TEXT, IdArticolo TEXT, Qta REAL
            );
        """, [
            ('INSERT INTO StoricoCassa VALUES (?, ?, ?, ?)', [
                ('2026-11-16', '01', '201', 7),
                ('2026-11-15', '01', '201', 4),
                ('2026-11-16', '90', '201', 50),
                ('2026-10-01', '02', '', 1),
            ]),
        ])
        _db(magx, """
            CREATE TABLE Tabacchi (IdRow INTEGER, Data TEXT, IdArticolo TEXT, Giacenza REAL);
        """, [
            ('INSERT INTO Tabacchi VALUES (?, ?, ?, ?)', [
                (1, '2026-11-15', '201', 10),
                (4, '2026-11-15', '201', 40),
                (2, '2026-10-19', '201', 7),
            ]),
        ])
        payload = extract_tabacchi_data(tabauno, storico, magx, '2026-11-17')
        self.assertEqual(payload['ultimo_giorno_chiuso'], '2026-11-16')
        self.assertEqual(payload['giorni_apertura'], ['2026-10-01', '2026-11-15', '2026-11-16'])
        self.assertEqual(len(payload['articoli']), 1)
        art = payload['articoli'][0]
        self.assertEqual(art['aams'], '201')
        self.assertEqual(art['descrizione'], 'CHESTERFIELD BLUE KS DA 20 A.')
        self.assertEqual(art['giacenza'], 96)
        self.assertEqual(art['vendite_giornaliere'], {'2026-11-15': 4.0, '2026-11-16': 7.0})
        self.assertEqual(art['giacenze_fine_giorno']['2026-11-15'], 40.0)
        self.assertEqual(art['giacenze_fine_giorno']['2026-10-19'], 7.0)
        self.assertTrue(payload['letto_alle'])


if __name__ == '__main__':
    unittest.main()
