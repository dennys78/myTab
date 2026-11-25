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
            CREATE TABLE Dispositivi (
                ID INTEGER, IdArticolo TEXT, Descrizione TEXT, Categoria TEXT,
                Prezzo1 REAL, MinimoOrdine REAL, Pacstecca REAL, Giacenza REAL
            );
        """, [
            ('INSERT INTO tabacchi VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
                (1, '201', 'CHESTERFIELD  BLUE  KS DA 20 A.', 'SIGARETTE', 5.8, 290, 200, 10),
                (9, '201', 'CHESTERFIELD BLUE KS DA 20 A.', 'SIGARETTE', 5.8, 290, 200, 96),
                (2, '999', 'SENZA VENDITE', 'SIGARETTE', 5, 250, 200, 5),
            ]),
            ('INSERT INTO Dispositivi VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
                (1, 'K0011', '11 - LEVIA RUBY WALTZ',
                 'PRODOTTI SENZA COMBUSTIONE - SOLIDI DIVERSI DA TABACCO', 5.5, 1, 10, 27),
                (2, 'V0PYU', 'VEEV ONE BLUE MINT', 'SIGARETTE ELETTRONICHE', 8.9, 1, 5, 10),
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
                ('2026-11-16', '20', 'K0011', 2),
                ('2026-11-15', '20', 'V0PYU', 1),
                ('2026-10-01', '02', '', 1),
            ]),
        ])
        _db(magx, """
            CREATE TABLE Tabacchi (IdRow INTEGER, Data TEXT, IdArticolo TEXT, Giacenza REAL);
            CREATE TABLE Dispositivi (IdRow INTEGER, Data TEXT, IdArticolo TEXT, Giacenza REAL);
        """, [
            ('INSERT INTO Tabacchi VALUES (?, ?, ?, ?)', [
                (1, '2026-11-15', '201', 10),
                (4, '2026-11-15', '201', 40),
                (2, '2026-10-19', '201', 7),
            ]),
            ('INSERT INTO Dispositivi VALUES (?, ?, ?, ?)', [
                (1, '2026-11-15', 'K0011', 20),
                (2, '2026-11-15', 'V0PYU', 8),
            ]),
        ])
        payload = extract_tabacchi_data(tabauno, storico, magx, '2026-11-17')
        self.assertEqual(payload['ultimo_giorno_chiuso'], '2026-11-16')
        self.assertEqual(payload['giorni_apertura'], ['2026-10-01', '2026-11-15', '2026-11-16'])
        by_aams = {art['aams']: art for art in payload['articoli']}
        self.assertEqual(set(by_aams), {'201', '999', 'K0011', 'V0PYU'})
        art = by_aams['201']
        self.assertEqual(art['descrizione'], 'CHESTERFIELD BLUE KS DA 20 A.')
        self.assertEqual(art['giacenza'], 96)
        self.assertEqual(art['tipo'], 'tabacco')
        self.assertEqual(art['vendite_giornaliere'], {'2026-11-15': 4.0, '2026-11-16': 7.0})
        self.assertEqual(art['giacenze_fine_giorno']['2026-11-15'], 40.0)
        self.assertEqual(art['giacenze_fine_giorno']['2026-10-19'], 7.0)
        self.assertEqual(by_aams['K0011']['tipo'], 'dispositivo')
        self.assertEqual(by_aams['K0011']['pacstecca'], 10)
        self.assertEqual(by_aams['K0011']['giacenze_fine_giorno']['2026-11-15'], 20.0)
        self.assertEqual(by_aams['V0PYU']['categoria'], 'SIGARETTE ELETTRONICHE')
        self.assertEqual(by_aams['999']['vendite_giornaliere'], {})
        self.assertTrue(payload['letto_alle'])
        ana = {row['aams']: row for row in payload['anagrafica']}
        self.assertEqual(set(ana), {'201', '999', 'K0011', 'V0PYU'})
        self.assertEqual(ana['999']['descrizione'], 'SENZA VENDITE')
        self.assertNotIn('vendite_giornaliere', ana['999'])


if __name__ == '__main__':
    unittest.main()
