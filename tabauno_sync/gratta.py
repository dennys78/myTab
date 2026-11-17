"""Lettura gratta e vinci da TabaUno, solo quando il portale la chiede. Non calcola i pacchi."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from .extract import TabaUnoError, _cleanup, _table, open_readonly

WINDOW_DAYS = 28


def _text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


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


def _latest_codes(rows):
    """Barcode di vendita più recente per IdArticolo."""
    best = {}
    for data, id_articolo, barcode, num in rows:
        day = _day(data)
        code = _text(barcode)
        article = _text(id_articolo)
        if not day or not code or not article:
            continue
        rank = (day, int(num or 0))
        current = best.get(article)
        if current is None or rank >= current[0]:
            best[article] = (rank, code)
    return {article: code for article, (_rank, code) in best.items()}


def extract_gratta_data(tabauno_db, storico_db, magx_db, oggi) -> dict:
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


def _read(main, storico, magx) -> dict:
    anagrafica_table, anagrafica_cols = _require(
        main,
        'GrattaeVinci',
        ('Barcode', 'Descrizione', 'Prezzo', 'Giacenza', 'MinimoOrdineNum', 'MinimoOrdineImp'),
    )
    link_table, _link_cols = _require(main, 'Gratta_Barcode', ('IdArticolo', 'G_Barcode'))
    sales_table, sales_cols = _require(
        storico, 'StoricoCassa', ('Data', 'IdArticolo', 'Barcode', 'Qta', 'CodiceSettore'),
    )
    stock_table, _stock_cols = _require(magx, 'Gratta', ('Data', 'IdArticolo', 'Giacenza', 'IdRow'))
    has_direct_id = 'IdArticolo' in anagrafica_cols
    has_num = 'Num' in sales_cols

    barcode_to_id = {}
    for id_articolo, barcode in main.execute(
        f'SELECT IdArticolo, G_Barcode FROM "{link_table}"'
    ):
        code = _text(barcode)
        article = _text(id_articolo)
        if code and article:
            barcode_to_id[code] = article

    id_select = 'IdArticolo' if has_direct_id else "''"
    anagrafica = {}
    for row in main.execute(
        f'''SELECT Barcode, Descrizione, Prezzo, Giacenza, MinimoOrdineNum, MinimoOrdineImp, {id_select}
            FROM "{anagrafica_table}"'''
    ):
        barcode, descrizione, prezzo, giacenza, biglietti, valore, direct_id = row
        article = _text(direct_id) or barcode_to_id.get(_text(barcode), '')
        if not article:
            continue
        current = anagrafica.get(article)
        stock = _num(giacenza)
        if current is not None and stock <= current['giacenza']:
            continue
        anagrafica[article] = {
            'id_articolo': article,
            'barcode_anagrafica': _text(barcode),
            'descrizione': _text(descrizione),
            'prezzo': _num(prezzo),
            'giacenza': stock,
            'biglietti_pacco': _num(biglietti),
            'valore_pacco': _num(valore),
        }

    ultimo_raw = storico.execute(f'SELECT MAX(Data) FROM "{sales_table}"').fetchone()[0]
    ultimo = _day(ultimo_raw)
    aperture = []
    for (raw,) in storico.execute(f'SELECT DISTINCT Data FROM "{sales_table}"'):
        day = _day(raw)
        if day:
            aperture.append(day)
    aperture.sort()

    vendite = {}
    if ultimo is not None:
        start = ultimo - timedelta(days=WINDOW_DAYS - 1)
        num_sql = 'Num' if has_num else '0'
        for data, id_articolo, qta in storico.execute(
            f'''SELECT Data, IdArticolo, SUM(Qta)
                FROM "{sales_table}"
                WHERE CodiceSettore = '90' AND Data >= ? AND Data <= ?
                GROUP BY Data, IdArticolo''',
            (_iso(start), _iso(ultimo)),
        ):
            day = _day(data)
            article = _text(id_articolo)
            qty = _num(qta)
            if day and article and qty > 0:
                vendite.setdefault(article, {})[_iso(day)] = float(qty)

        latest = _latest_codes(storico.execute(
            f'''SELECT Data, IdArticolo, Barcode, {num_sql}
                FROM "{sales_table}" WHERE CodiceSettore = '90' '''
        ))
    else:
        latest = {}

    giacenze = {}
    if ultimo is not None:
        stock_start = ultimo - timedelta(days=WINDOW_DAYS)
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
        for (article, day), (_rank, stock) in chosen.items():
            giacenze.setdefault(article, {})[day] = float(stock)

    start = ultimo - timedelta(days=WINDOW_DAYS - 1) if ultimo else None
    giochi = []
    for article, info in anagrafica.items():
        sales = vendite.get(article, {})
        in_window = bool(sales) if start else False
        if not in_window and info['giacenza'] <= 0:
            continue
        giochi.append({
            'id_articolo': article,
            'codice': latest.get(article) or info['barcode_anagrafica'],
            'descrizione': info['descrizione'],
            'prezzo': float(info['prezzo']),
            'biglietti_pacco': float(info['biglietti_pacco']),
            'valore_pacco': float(info['valore_pacco']),
            'giacenza': float(info['giacenza']),
            'vendite_giornaliere': sales,
            'giacenze_fine_giorno': giacenze.get(article, {}),
        })
    giochi.sort(key=lambda item: (item['codice'], item['id_articolo']))
    return {
        'giochi': giochi,
        'giorni_apertura': [_iso(day) for day in aperture],
        'ultimo_giorno_chiuso': _iso(ultimo) if ultimo else None,
        'letto_alle': datetime.now().astimezone().isoformat(timespec='seconds'),
    }
