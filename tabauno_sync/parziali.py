"""Lettura parziali di cassa (giornata aperta) da cassagiorno — solo lettura, connessione breve."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .extract import TabaUnoError, _cleanup, _table, open_readonly


def _text(value) -> str:
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    if text.endswith('.0') and text[:-2].isdigit():
        return text[:-2]
    return text


def _num(value) -> float:
    if value is None or value == '':
        return 0.0
    return float(Decimal(str(value)))


def _ora(value) -> str:
    text = _text(value)
    if not text:
        return ''
    # Accetta HH:MM, HH:MM:SS, o timestamp ISO.
    if 'T' in text:
        text = text.split('T', 1)[1]
    text = text.replace('.', ':')
    parti = text.split(':')
    if len(parti) >= 2 and parti[0].isdigit() and parti[1].isdigit():
        return f'{int(parti[0]):02d}:{int(parti[1]):02d}'
    return text[:5]


def _require(connection, table, columns):
    real = _table(connection, table)
    if not real:
        raise TabaUnoError(f'Tabella {table} assente.')
    found = {row[1] for row in connection.execute(f'PRAGMA table_info("{real}")')}
    missing = [name for name in columns if name not in found]
    if missing:
        raise TabaUnoError(f'{table}: mancano le colonne {", ".join(missing)}.')
    return real, found


def extract_parziali_cassa(tabauno_db) -> dict:
    """Aggrega cassagiorno per CodiceSettore. Connessione RO breve."""
    conn = open_readonly(tabauno_db)
    try:
        cassa, _ = _require(conn, 'cassagiorno', ('CodiceSettore', 'Importo', 'Data', 'Ora'))
        settori_tbl = _table(conn, 'settori')
        nomi = {}
        if settori_tbl:
            cols = {row[1] for row in conn.execute(f'PRAGMA table_info("{settori_tbl}")')}
            if 'CodiceSettore' in cols and 'Descrizione' in cols:
                for row in conn.execute(
                    f'SELECT CodiceSettore, Descrizione FROM "{settori_tbl}"'
                ):
                    codice = _text(row[0])
                    if codice:
                        nomi[codice] = ' '.join(_text(row[1]).split()) or codice

        aggregati = list(conn.execute(
            f'''
            SELECT CodiceSettore, COUNT(*), SUM(Importo)
            FROM "{cassa}"
            GROUP BY CodiceSettore
            ORDER BY CodiceSettore
            '''
        ))
        meta = conn.execute(
            f'SELECT MIN(Data), MAX(Data), MAX(Ora), COUNT(*) FROM "{cassa}"'
        ).fetchone()
        data_min = _text(meta[0])[:10] if meta and meta[0] is not None else ''
        data_max = _text(meta[1])[:10] if meta and meta[1] is not None else ''
        ultima_ora = _ora(meta[2]) if meta else ''
        righe_totali = int(meta[3] or 0) if meta else 0
        data = data_max or data_min or ''

        settori = []
        for codice_raw, n, importo in aggregati:
            codice = _text(codice_raw)
            if not codice:
                continue
            settori.append({
                'codice': codice,
                'descrizione': nomi.get(codice) or codice,
                'n': int(n or 0),
                'importo': round(_num(importo), 2),
            })

        return {
            'data': data,
            'ultima_ora': ultima_ora,
            'righe_totali': righe_totali,
            'settori': settori,
            'letto_alle': datetime.now().astimezone().isoformat(timespec='seconds'),
        }
    finally:
        _cleanup(conn)
