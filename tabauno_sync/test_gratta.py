import sqlite3
import tempfile
import unittest
from pathlib import Path

from tabauno_sync.gratta import extract_gratta_data


def _db(path, script, rows=()):
    connection = sqlite3.connect(path)
    connection.executescript(script)
    for sql, values in rows:
        connection.executemany(sql, values)
    connection.commit()
    connection.close()


class ExtractGrattaTests(unittest.TestCase):
    def test_codice_anagrafica_diverso_dal_codice_vendite(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        tabauno = root / 'TabaUno.db'
        storico = root / 'TabaUnoStorico.db'
        magx = root / 'Db_MagX.db'
        _db(tabauno, """
            CREATE TABLE GrattaeVinci (
                Barcode TEXT, Descrizione TEXT, Prezzo REAL, Giacenza REAL,
                MinimoOrdineNum REAL, MinimoOrdineImp REAL
            );
            CREATE TABLE Gratta_Barcode (IdArticolo TEXT, G_Barcode TEXT);
        """, [
            ('INSERT INTO GrattaeVinci VALUES (?, ?, ?, ?, ?, ?)', [
                ('3311', 'NUMERISSIMI', 5, 112, 60, 300),
                ('9999', 'ESAURITO', 1, 0, 10, 10),
            ]),
            ('INSERT INTO Gratta_Barcode VALUES (?, ?)', [
                ('27-NUMERISSIMI', '3311'),
                ('27-NUMERISSIMI', '3325'),
            ]),
        ])
        _db(storico, """
            CREATE TABLE StoricoCassa (
                Data TEXT, CodiceSettore TEXT, IdArticolo TEXT, Barcode TEXT, Qta REAL, Num INTEGER
            );
        """, [
            ('INSERT INTO StoricoCassa VALUES (?, ?, ?, ?, ?, ?)', [
                ('2026-11-16', '01', '', '', 1, 1),
                ('2026-11-15', '90', '27-NUMERISSIMI', '3311', 2, 2),
                ('2026-11-16', '90', '27-NUMERISSIMI', '3325', 3, 3),
                ('2026-10-01', '90', '27-NUMERISSIMI', '3311', 9, 1),
            ]),
        ])
        _db(magx, """
            CREATE TABLE Gratta (IdRow INTEGER, Data TEXT, IdArticolo TEXT, Giacenza REAL);
        """, [
            ('INSERT INTO Gratta VALUES (?, ?, ?, ?)', [
                (1, '2026-11-15', '27-NUMERISSIMI', 10),
                (4, '2026-11-15', '27-NUMERISSIMI', 40),
                (2, '2026-10-19', '27-NUMERISSIMI', 7),
            ]),
        ])
        payload = extract_gratta_data(tabauno, storico, magx, '2026-11-17')
        self.assertEqual(payload['ultimo_giorno_chiuso'], '2026-11-16')
        self.assertEqual(payload['giorni_apertura'], ['2026-10-01', '2026-11-15', '2026-11-16'])
        self.assertEqual(len(payload['giochi']), 1)
        gioco = payload['giochi'][0]
        self.assertEqual(gioco['id_articolo'], '27-NUMERISSIMI')
        self.assertEqual(gioco['codice'], '3325')
        self.assertEqual(gioco['descrizione'], 'NUMERISSIMI')
        self.assertEqual(gioco['giacenza'], 112)
        self.assertEqual(gioco['vendite_giornaliere'], {'2026-11-15': 2.0, '2026-11-16': 3.0})
        self.assertEqual(gioco['giacenze_fine_giorno']['2026-11-15'], 40.0)
        self.assertEqual(gioco['giacenze_fine_giorno']['2026-10-19'], 7.0)
        self.assertTrue(payload['letto_alle'])
