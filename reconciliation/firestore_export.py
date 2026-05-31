"""Parser per export gestiti di Cloud Firestore / Datastore.

Gli export prodotti da `gcloud firestore export` (o dalla console) sono file in
formato **LevelDB log** i cui record contengono entità serializzate con il
vecchio protobuf `storage_onestore_v3.EntityProto` (Datastore v3).

Questo modulo non dipende da Django e ricostruisce, per ogni documento, una
coppia ``(doc_id, kind, doc_data)`` dove ``doc_data`` ha la stessa forma del
``DocumentSnapshot.to_dict()`` restituito da Firestore live. In questo modo il
mapping verso i modelli myTaba può riusare ``firebase_import``.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone

# --- formato LevelDB log -----------------------------------------------------
_BLOCK_SIZE = 32768
_HEADER_SIZE = 7  # crc32 (4) + length (2, little endian) + type (1)

_REC_FULL = 1
_REC_FIRST = 2
_REC_MIDDLE = 3
_REC_LAST = 4


def read_leveldb_records(data: bytes):
    """Genera i payload (bytes) dei record di un file LevelDB log."""
    pos = 0
    n = len(data)
    pending = bytearray()
    while pos + _HEADER_SIZE <= n:
        block_remaining = _BLOCK_SIZE - (pos % _BLOCK_SIZE)
        if block_remaining < _HEADER_SIZE:
            pos += block_remaining  # padding di fine blocco
            continue

        _crc, length, rtype = struct.unpack('<IHB', data[pos:pos + _HEADER_SIZE])
        pos += _HEADER_SIZE
        chunk = data[pos:pos + length]
        pos += length

        if rtype == _REC_FULL:
            yield bytes(chunk)
        elif rtype == _REC_FIRST:
            pending = bytearray(chunk)
        elif rtype == _REC_MIDDLE:
            pending += chunk
        elif rtype == _REC_LAST:
            pending += chunk
            yield bytes(pending)
            pending = bytearray()
        # rtype == 0 (zero/padding) → ignorato


# --- protobuf wire format generico ------------------------------------------
def _read_varint(buf: bytes, i: int):
    result = 0
    shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, i
        shift += 7


def _read_group(buf: bytes, i: int):
    """Legge un gruppo (wire type 3) e ritorna (bytes_interni, posizione_dopo_end)."""
    start = i
    depth = 1
    while i < len(buf):
        tag, j = _read_varint(buf, i)
        wt = tag & 7
        if wt == 3:
            depth += 1
            i = j
        elif wt == 4:
            depth -= 1
            if depth == 0:
                return buf[start:i], j
            i = j
        elif wt == 0:
            _, i = _read_varint(buf, j)
        elif wt == 1:
            i = j + 8
        elif wt == 2:
            ln, k = _read_varint(buf, j)
            i = k + ln
        elif wt == 5:
            i = j + 4
        else:
            raise ValueError(f'wire type inatteso {wt} nel gruppo')
    raise ValueError('gruppo non terminato')


def _parse_message(buf: bytes):
    """Ritorna lista di (field_number, wire_type, value)."""
    fields = []
    i = 0
    n = len(buf)
    while i < n:
        tag, i = _read_varint(buf, i)
        field = tag >> 3
        wt = tag & 7
        if wt == 0:
            val, i = _read_varint(buf, i)
        elif wt == 1:
            val = buf[i:i + 8]
            i += 8
        elif wt == 2:
            ln, i = _read_varint(buf, i)
            val = buf[i:i + ln]
            i += ln
        elif wt == 5:
            val = buf[i:i + 4]
            i += 4
        elif wt == 3:
            val, i = _read_group(buf, i)
        elif wt == 4:
            continue  # end group spurio
        else:
            raise ValueError(f'wire type inatteso {wt}')
        fields.append((field, wt, val))
    return fields


# --- mapping EntityProto v3 --------------------------------------------------
# EntityProto
_E_KEY = 13
_E_PROPERTY = 14
_E_RAW_PROPERTY = 15
# Reference / Path
_REF_PATH = 14
_PATH_ELEMENT = 1
_ELEM_TYPE = 2
_ELEM_ID = 3
_ELEM_NAME = 4
# Property
_P_MEANING = 1
_P_NAME = 3
_P_MULTIPLE = 4
_P_VALUE = 5
# PropertyValue
_PV_INT64 = 1
_PV_BOOL = 2
_PV_STRING = 3
_PV_DOUBLE = 4
# Meaning
_M_GD_WHEN = 7
_M_ENTITY_PROTO = 19


def _parse_property_value(buf: bytes, meaning: int):
    kind = None
    value = None
    for field, _wt, val in _parse_message(buf):
        if field == _PV_INT64:
            kind, value = 'int', val
        elif field == _PV_BOOL:
            kind, value = 'bool', bool(val)
        elif field == _PV_STRING:
            kind, value = 'string', val
        elif field == _PV_DOUBLE:
            kind, value = 'double', struct.unpack('<d', val)[0]

    if kind is None:
        return None
    if meaning == _M_ENTITY_PROTO and kind == 'string':
        _doc_id, _kind, nested = parse_entity(value)
        return nested
    if meaning == _M_GD_WHEN and kind == 'int':
        return datetime.fromtimestamp(value / 1_000_000, tz=timezone.utc)
    if kind == 'string':
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return value
    return value


def _parse_property(buf: bytes):
    meaning = 0
    name = None
    multiple = False
    raw_value = None
    for field, _wt, val in _parse_message(buf):
        if field == _P_MEANING:
            meaning = val
        elif field == _P_NAME:
            name = val.decode('utf-8')
        elif field == _P_MULTIPLE:
            multiple = bool(val)
        elif field == _P_VALUE:
            raw_value = val
    value = _parse_property_value(raw_value, meaning) if raw_value is not None else None
    return name, value, multiple


def _parse_reference_path(buf: bytes):
    """Ritorna lista di (kind, id, name) dagli Element del path."""
    elements = []
    for field, wt, val in _parse_message(buf):
        if field == _REF_PATH:
            for ef, _ewt, ev in _parse_message(val):
                if ef == _PATH_ELEMENT:
                    elements.append(_parse_path_element(ev))
    return elements


def _parse_path_element(buf: bytes):
    kind = None
    id_ = None
    name = None
    for field, _wt, val in _parse_message(buf):
        if field == _ELEM_TYPE:
            kind = val.decode('utf-8')
        elif field == _ELEM_ID:
            id_ = val
        elif field == _ELEM_NAME:
            name = val.decode('utf-8')
    return kind, id_, name


def parse_entity(buf: bytes):
    """Converte un EntityProto serializzato in ``(doc_id, kind, doc_data)``."""
    doc_id = None
    kind = None
    data: dict = {}
    for field, _wt, val in _parse_message(buf):
        if field == _E_KEY:
            path = _parse_reference_path(val)
            if path:
                kind, elem_id, name = path[-1]
                doc_id = name or (str(elem_id) if elem_id is not None else None)
        elif field in (_E_PROPERTY, _E_RAW_PROPERTY):
            name, value, multiple = _parse_property(val)
            if name is None:
                continue
            if multiple:
                bucket = data.get(name)
                if not isinstance(bucket, list):
                    bucket = []
                    data[name] = bucket
                bucket.append(value)
            else:
                data[name] = value
    return doc_id, kind, data


def prepare_doc_data(doc_data: dict) -> dict:
    """Normalizza il documento prima del mapping verso i modelli myTaba.

    Nell'app "Gestione incassi tabaccheria" i reparti gioco compaiono sia in
    ``vociDiCassa`` (lista completa di tutti i reparti) sia nei campi top-level
    ridondanti ``datiGV/datiLottomatica/datiSisal/datiTabacchi``. Se la lista
    ``vociDiCassa`` è presente e popolata, rimuoviamo i campi ``dati*`` per
    evitare il doppio conteggio di LOTTOMATICA/SISAL/GRATTA E VINCI.
    """
    voci = doc_data.get('vociDiCassa')
    has_voci = isinstance(voci, list) and any(isinstance(v, dict) for v in voci)
    if not has_voci:
        return doc_data
    return {
        key: value
        for key, value in doc_data.items()
        if not (key.startswith('dati') and isinstance(value, dict))
    }


def iter_export_documents(data: bytes, collection: str | None = None):
    """Genera ``(doc_id, doc_data)`` per ogni entità dell'export.

    Se ``collection`` è valorizzato, filtra per kind corrispondente.
    """
    for record in read_leveldb_records(data):
        try:
            doc_id, kind, doc_data = parse_entity(record)
        except (ValueError, IndexError, struct.error):
            continue
        if not doc_data:
            continue
        if collection and kind and kind != collection:
            continue
        yield doc_id, doc_data
