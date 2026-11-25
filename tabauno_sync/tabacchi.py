"""Lettura tabacchi e dispositivi/solidi da TabaUno, solo quando il portale la chiede.

Non calcola le stecche/confezioni: restituisce anagrafica, vendite e giacenze.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from .extract import TabaUnoError, _cleanup, _table, open_readonly

WINDOW_DAYS = 28
SETTORE_TABACCHI = '01'
SETTORE_DISPOSITIVI = '20'


def _text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


def _descrizione(value) -> str:
    return ' '.join(_text(value).split())


def _num(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0')
    return Decimal(str(value))


def _day(value):
    text = _text(value)
    if len(text) < 10:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _iso(day: date) -> str:
    return day.isoformat()


def _require(connection, table, columns):
    real = _table(connection, table)
    if not real:
        raise TabaUnoError(f'Tabella {table} assente.')
    found = {row[1] for row in connection.execute(f'PRAGMA table_info("{real}")')}
    missing = [name for name in columns if name not in found]
    if missing:
        raise TabaUnoError(f'{table}: mancano le colonne {", ".join(missing)}.')
    return real, found


def extract_tabacchi_data(tabauno_db, storico_db, magx_db, oggi) -> dict:
    """Legge anagrafica, vendite e giacenze. oggi è la data della richiesta, non il periodo."""
    _day(oggi)
    main = open_readonly(tabauno_db)
    storico = None
    magx = None
    try:
        if not storico_db:
            raise TabaUnoError('Database storico non indicato.')
        if not magx_db:
            raise TabaUnoError('Database magazzino non indicato.')
        storico = open_readonly(storico_db)
        magx = open_readonly(magx_db)
        return _read(main, storico, magx)
    finally:
        _cleanup(main)
        if storico is not None:
            _cleanup(storico)
        if magx is not None:
            _cleanup(magx)


def _read_anagrafica_tabacchi(main) -> dict:
    anagrafica_table, _cols = _require(
        main,
        'tabacchi',
        ('CodiceAams', 'Descrizione', 'Categoria', 'Prezzo', 'PrezzoKG', 'MinimoOrdine', 'Giacenza', 'ID'),
    )
    anagrafica = {}
    for codice, descrizione, categoria, prezzo, prezzo_kg, minimo, giacenza, row_id in main.execute(
        f'''SELECT CodiceAams, Descrizione, Categoria, Prezzo, PrezzoKG, MinimoOrdine, Giacenza, ID
            FROM "{anagrafica_table}"'''
    ):
        aams = _text(codice)
        if not aams:
            continue
        rank = int(row_id or 0)
        current = anagrafica.get(aams)
        if current is not None and rank < current['_id']:
            continue
        anagrafica[aams] = {
            'aams': aams,
            'descrizione': _descrizione(descrizione),
            'categoria': _text(categoria),
            'prezzo': _num(prezzo),
            'prezzo_kg': _num(prezzo_kg),
            'minimo_grammi': _num(minimo),
            'pacstecca': 0,
            'giacenza': _num(giacenza),
            'tipo': 'tabacco',
            '_id': rank,
        }
    return anagrafica


def _read_anagrafica_dispositivi(main) -> dict:
    try:
        table, cols = _require(
            main,
            'Dispositivi',
            ('IdArticolo', 'Descrizione', 'Categoria', 'Prezzo1', 'MinimoOrdine', 'Pacstecca', 'Giacenza', 'ID'),
        )
    except TabaUnoError:
        return {}
    has_gia = 'Giacenza' in cols
    anagrafica = {}
    select = (
        'ID, IdArticolo, Descrizione, Categoria, Prezzo1, MinimoOrdine, Pacstecca, Giacenza'
        if has_gia else
        'ID, IdArticolo, Descrizione, Categoria, Prezzo1, MinimoOrdine, Pacstecca, 0'
    )
    for row_id, codice, descrizione, categoria, prezzo, minimo, pacstecca, giacenza in main.execute(
        f'SELECT {select} FROM "{table}"'
    ):
        aams = _text(codice)
        if not aams:
            continue
        rank = int(row_id or 0)
        current = anagrafica.get(aams)
        if current is not None and rank < current['_id']:
            continue
        anagrafica[aams] = {
            'aams': aams,
            'descrizione': _descrizione(descrizione),
            'categoria': _text(categoria),
            'prezzo': _num(prezzo),
            'prezzo_kg': Decimal('0'),
            'minimo_grammi': _num(minimo),
            'pacstecca': int(_num(pacstecca)),
            'giacenza': _num(giacenza),
            'tipo': 'dispositivo',
            '_id': rank,
        }
    return anagrafica


def _read_vendite(storico, settori, start, ultimo) -> dict:
    sales_table, _sales_cols = _require(
        storico, 'StoricoCassa', ('Data', 'IdArticolo', 'Qta', 'CodiceSettore'),
    )
    placeholders = ','.join('?' for _ in settori)
    vendite = {}
    for data, id_articolo, qta in storico.execute(
        f'''SELECT Data, IdArticolo, SUM(Qta)
            FROM "{sales_table}"
            WHERE CodiceSettore IN ({placeholders}) AND Data >= ? AND Data <= ?
            GROUP BY Data, IdArticolo''',
        (*settori, _iso(start), _iso(ultimo)),
    ):
        day = _day(data)
        article = _text(id_articolo)
        qty = _num(qta)
        if day and article and qty > 0:
            vendite.setdefault(article, {})[_iso(day)] = float(qty)
    return vendite


def _read_giacenze(magx, table_name, stock_start, ultimo) -> dict:
    try:
        stock_table, _stock_cols = _require(
            magx, table_name, ('Data', 'IdArticolo', 'Giacenza', 'IdRow'),
        )
    except TabaUnoError:
        return {}
    chosen = {}
    for id_row, data, id_articolo, giacenza in magx.execute(
        f'''SELECT IdRow, Data, IdArticolo, Giacenza FROM "{stock_table}"
            WHERE Data >= ? AND Data <= ?''',
        (_iso(stock_start), _iso(ultimo)),
    ):
        day = _day(data)
        article = _text(id_articolo)
        if not day or not article:
            continue
        key = (article, _iso(day))
        rank = int(id_row or 0)
        current = chosen.get(key)
        if current is None or rank >= current[0]:
            chosen[key] = (rank, _num(giacenza))
    giacenze = {}
    for (article, day), (_rank, stock) in chosen.items():
        giacenze.setdefault(article, {})[day] = float(stock)
    return giacenze


def _read(main, storico, magx) -> dict:
    anagrafica = _read_anagrafica_tabacchi(main)
    dispositivi = _read_anagrafica_dispositivi(main)
    for aams, info in dispositivi.items():
        # I codici dispositivo non devono sovrascrivere i tabacchi AAMS.
        anagrafica.setdefault(aams, info)

    sales_table, _sales_cols = _require(
        storico, 'StoricoCassa', ('Data', 'IdArticolo', 'Qta', 'CodiceSettore'),
    )
    ultimo_raw = storico.execute(f'SELECT MAX(Data) FROM "{sales_table}"').fetchone()[0]
    ultimo = _day(ultimo_raw)
    aperture = []
    for (raw,) in storico.execute(f'SELECT DISTINCT Data FROM "{sales_table}"'):
        day = _day(raw)
        if day:
            aperture.append(day)
    aperture.sort()

    vendite = {}
    giacenze = {}
    if ultimo is not None:
        start = ultimo - timedelta(days=WINDOW_DAYS - 1)
        stock_start = ultimo - timedelta(days=WINDOW_DAYS)
        vendite = _read_vendite(
            storico,
            (SETTORE_TABACCHI, SETTORE_DISPOSITIVI),
            start,
            ultimo,
        )
        giacenze_taba = _read_giacenze(magx, 'Tabacchi', stock_start, ultimo)
        giacenze_dsp = _read_giacenze(magx, 'Dispositivi', stock_start, ultimo)
        giacenze = {**giacenze_taba, **giacenze_dsp}

    def _scheda(info):
        return {
            'aams': info['aams'],
            'descrizione': info['descrizione'],
            'categoria': info['categoria'],
            'tipo': info.get('tipo') or 'tabacco',
            'prezzo': float(info['prezzo']),
            'prezzo_kg': float(info['prezzo_kg']),
            'minimo_grammi': float(info['minimo_grammi']),
            'pacstecca': int(info.get('pacstecca') or 0),
            'giacenza': float(info['giacenza']),
        }

    catalogo = [_scheda(info) for info in anagrafica.values()]
    catalogo.sort(key=lambda item: (item['descrizione'], item['aams']))

    # Tutti i codici in anagrafica: con vendite (statistica) o senza (fuori statistica).
    articoli = []
    for aams, info in anagrafica.items():
        scheda = _scheda(info)
        scheda['vendite_giornaliere'] = vendite.get(aams) or {}
        scheda['giacenze_fine_giorno'] = giacenze.get(aams, {})
        articoli.append(scheda)
    articoli.sort(key=lambda item: (item['descrizione'], item['aams']))
    return {
        'articoli': articoli,
        'anagrafica': catalogo,
        'giorni_apertura': [_iso(day) for day in aperture],
        'ultimo_giorno_chiuso': _iso(ultimo) if ultimo else None,
        'letto_alle': datetime.now().astimezone().isoformat(timespec='seconds'),
    }
