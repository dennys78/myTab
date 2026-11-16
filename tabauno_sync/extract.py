"""Chiusura di cassa da TabaUno.db / TabaUnoStorico.db, solo in lettura."""

from __future__ import annotations

import sqlite3
import tempfile
import time
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal('0.01')
ZERO = Decimal('0')
GRATTA_WIN_DESC = 'VINCITE GRATTA E VINCI'
GRATTA_CODE = '90'
GESTORE_CODE = '97'
_SNAPSHOTS = {}


class TabaUnoError(Exception):
    pass


def _money(value) -> Decimal:
    if value is None or value == '':
        return ZERO
    if isinstance(value, Decimal):
        amount = value
    else:
        amount = Decimal(str(value))
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _raw(value) -> Decimal:
    if value is None or value == '':
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _num(value: Decimal) -> float:
    return float(_money(value))


def _sqlite_ro_uri(path: Path) -> str:
    return f'{path.resolve().as_uri()}?mode=ro'


def _cleanup(connection):
    temp_path = _SNAPSHOTS.pop(id(connection), None)
    connection.close()
    if temp_path:
        Path(temp_path).unlink(missing_ok=True)


def _connect_ro(source: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(_sqlite_ro_uri(source), uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA query_only = ON')
    connection.execute('PRAGMA busy_timeout = 5000')
    return connection


def open_readonly(path, *, snapshot=False) -> sqlite3.Connection:
    """Apre il DB in sola lettura, per poco. Lo snapshot completo è solo un'opzione di debug."""
    source = Path(path)
    if not source.is_file():
        raise TabaUnoError(f'Database non trovato: {source}')
    if snapshot:
        return _open_snapshot(source)

    delays = (0.5, 1.0, 2.0)
    last_error = None
    for attempt in range(3):
        try:
            return _connect_ro(source)
        except sqlite3.OperationalError as exc:
            last_error = exc
            if 'locked' not in str(exc).lower() or attempt == 2:
                break
            time.sleep(delays[attempt])
    if last_error is not None and 'locked' in str(last_error).lower():
        raise TabaUnoError(
            'Database TabaUno occupato da una scrittura. Riprova tra qualche secondo.'
        ) from last_error
    raise TabaUnoError(f'Impossibile aprire {source}: {last_error}') from last_error


def _open_snapshot(source: Path) -> sqlite3.Connection:
    handle = tempfile.NamedTemporaryFile(prefix='tabauno_', suffix='.db', delete=False)
    snapshot_path = handle.name
    handle.close()
    origin = _connect_ro(source)
    try:
        copy = sqlite3.connect(snapshot_path)
        try:
            origin.backup(copy)
        finally:
            copy.close()
    finally:
        origin.close()
    connection = sqlite3.connect(_sqlite_ro_uri(Path(snapshot_path)), uri=True)
    connection.row_factory = sqlite3.Row
    _SNAPSHOTS[id(connection)] = snapshot_path
    return connection


def _tables(connection) -> dict:
    found = {}
    for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        found[name.lower()] = name
    return found


def _table(connection, *candidates):
    names = _tables(connection)
    for candidate in candidates:
        real = names.get(candidate.lower())
        if real:
            return real
    return None


def _rows(connection, table, day):
    if not table:
        return []
    return list(connection.execute(
        f'SELECT CodiceSettore, Descrizione, Importo, RagioneSociale FROM "{table}" WHERE Data = ?',
        (day,),
    ))


def _lookup(connection, table, key_column, value_column):
    if not table:
        return {}
    values = {}
    for row in connection.execute(f'SELECT "{key_column}", "{value_column}" FROM "{table}"'):
        key = str(row[0] or '').strip()
        if key:
            values[key] = str(row[1] or '').strip()
    return values


def _conto(connection, table, day):
    if not table:
        return None
    row = connection.execute(
        f'SELECT Incassi, Pos, Contanti FROM "{table}" WHERE Data = ?',
        (day,),
    ).fetchone()
    if row is None:
        return None
    return {
        'pos': _money(row['Pos']),
        'contanti': _money(row['Contanti']),
        'totale': _money(row['Incassi']),
    }


def _sort_key(voce):
    kind_rank = {'vendita': 0, 'gestore': 1, 'movimento': 2, 'sconosciuto': 3}
    return (kind_rank[voce['kind']], voce['order'], voce['descrizione'])


def _is_gratta_win(code, description, ragione, amount) -> bool:
    return (
        code == '300'
        and description.upper() == GRATTA_WIN_DESC
        and ragione.upper() == 'LOTTOMATICA'
        and amount < 0
    )


def extract_closure(db_path, day, *, storico_path=None, gratta='B', snapshot=False) -> dict:
    """Aggrega la chiusura del giorno. gratta='B' sposta le vincite Gratta sul reparto 90."""
    rule = str(gratta or 'B').strip().upper()
    if rule not in {'A', 'B'}:
        raise TabaUnoError("Regola Gratta non valida: usa 'A' o 'B'.")
    day = str(day).strip()
    if len(day) != 10:
        raise TabaUnoError('Data non valida, usa YYYY-MM-DD.')

    main = open_readonly(db_path, snapshot=snapshot)
    storico = None
    try:
        live_table = _table(main, 'cassaglobal')
        rows = _rows(main, live_table, day)
        source = 'cassaglobal'
        catalog = main
        today = date.today().isoformat()
        if not rows and day < today and storico_path and Path(storico_path).is_file():
            storico = open_readonly(storico_path, snapshot=snapshot)
            history_table = _table(storico, 'CassaGlobal', 'cassaglobal')
            rows = _rows(storico, history_table, day)
            source = 'CassaGlobal' if rows else source

        settori = _lookup(catalog, _table(catalog, 'settori'), 'CodiceSettore', 'Descrizione')
        movimenti = _lookup(
            catalog, _table(catalog, 'MovimentiCassa'), 'CodiceMovimentoCassa', 'DescrizioneMovimento',
        )
        conto = _conto(catalog, _table(catalog, 'conto'), day)
        pending_close = day == today and (not rows or conto is None)
        if pending_close:
            rows = []
        payload = _aggregate(day, rows, settori, movimenti, conto, rule, source)
        payload['verifiche']['chiusura_eseguita'] = conto is not None
        payload['verifiche']['messaggio'] = (
            'Chiusura non ancora eseguita in TabaUno per questa data' if pending_close else ''
        )
        return payload
    finally:
        _cleanup(main)
        if storico is not None:
            _cleanup(storico)


def _aggregate(day, rows, settori, movimenti, conto, rule, source) -> dict:
    buckets = {}
    unknown = []
    movement_total = ZERO

    def add(key, code, description, amount, kind, order):
        bucket = buckets.get(key)
        if bucket is None:
            bucket = buckets[key] = {
                'reparto': code,
                'descrizione': description,
                'entrate': ZERO,
                'uscite': ZERO,
                'kind': kind,
                'order': order,
            }
        if amount > 0:
            bucket['entrate'] += amount
        elif amount < 0:
            bucket['uscite'] += -amount

    for row in rows:
        amount = _raw(row['Importo'])
        movement_total += amount
        code = str(row['CodiceSettore'] or '').strip()
        description = str(row['Descrizione'] or '').strip()
        ragione = str(row['RagioneSociale'] or '').strip()
        if rule == 'B' and _is_gratta_win(code, description, ragione, amount):
            gratta_name = settori.get(GRATTA_CODE) or 'GRATTA E VINCI'
            add(GRATTA_CODE, GRATTA_CODE, gratta_name, amount, 'vendita', 90)
            continue
        if ragione:
            add(f'G:{ragione.upper()}', GESTORE_CODE, ragione, amount, 'gestore', 0)
            continue
        sector_name = settori.get(code, '')
        if sector_name:
            order = int(code) if code.isdigit() else 10**6
            add(code, code, sector_name, amount, 'vendita', order)
            continue
        movement_name = movimenti.get(code, '')
        if movement_name:
            order = int(code) if code.isdigit() else 10**6
            add(f'M:{code}', code, movement_name, amount, 'movimento', order)
            continue
        if code and code not in unknown:
            unknown.append(code)
        order = int(code) if code.isdigit() else 10**6
        add(f'U:{code}', code, f'CODICE {code}', amount, 'sconosciuto', order)

    voci = []
    for bucket in sorted(buckets.values(), key=_sort_key):
        entrate = _money(bucket['entrate'])
        uscite = _money(bucket['uscite'])
        if entrate == 0 and uscite == 0:
            continue
        voci.append({
            'reparto': bucket['reparto'],
            'descrizione': bucket['descrizione'],
            'entrate': _num(entrate),
            'uscite': _num(uscite),
            'saldo': _num(entrate - uscite),
        })

    totale_entrate = _money(sum((_raw(voce['entrate']) for voce in voci), ZERO))
    totale_uscite = _money(sum((_raw(voce['uscite']) for voce in voci), ZERO))
    totale_saldo = _money(totale_entrate - totale_uscite)
    if conto is None:
        incasso = {'pos': None, 'contanti': None, 'totale': None}
        saldo_ok = False
        split_ok = False
    else:
        incasso = {
            'pos': _num(conto['pos']),
            'contanti': _num(conto['contanti']),
            'totale': _num(conto['totale']),
        }
        saldo_ok = abs(totale_saldo - conto['totale']) <= CENT
        split_ok = abs((conto['pos'] + conto['contanti']) - conto['totale']) <= CENT

    return {
        'data': day,
        'voci': voci,
        'totale': {
            'entrate': _num(totale_entrate),
            'uscite': _num(totale_uscite),
            'saldo': _num(totale_saldo),
        },
        'incasso': incasso,
        'verifiche': {
            'saldo_uguale_incasso': saldo_ok,
            'pos_piu_contanti_ok': split_ok,
            'saldo_uguale_movimenti': abs(totale_saldo - _money(movement_total)) <= CENT,
            'codici_sconosciuti': unknown,
            'senza_righe': not rows,
            'sorgente': source,
        },
    }
