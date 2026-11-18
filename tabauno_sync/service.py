"""Agente sul PC del negozio: legge TabaUno solo quando il portale lo chiede."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .extract import TabaUnoError, extract_closure
from .gratta import extract_gratta_data
from .tabacchi import extract_tabacchi_data

_BACKOFF = (10, 30, 60, 300)


def load_config(path) -> dict:
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not config.get('tabauno_db'):
        raise TabaUnoError('Config: manca tabauno_db.')
    if not str(config.get('mytab_url') or '').strip():
        raise TabaUnoError('Config: manca mytab_url.')
    if not str(config.get('agent_token') or '').strip():
        raise TabaUnoError('Config: manca agent_token.')
    config.setdefault('storico_db', '')
    config.setdefault('magx_db', '')
    config.setdefault('gratta', 'B')
    config.setdefault('poll_seconds', 10)
    config.setdefault('log_dir', 'logs')
    config.setdefault('ordine_logista_path', '')
    return config


def ordine_logista_path(config) -> Path:
    configured = str(config.get('ordine_logista_path') or '').strip()
    if configured:
        return Path(configured)
    return Path(config['tabauno_db']).resolve().parent / 'Ordine_Logista.xls'


def _logger(config) -> logging.Logger:
    log_dir = Path(config.get('log_dir') or 'logs')
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger('tabauno_agent')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.handlers.RotatingFileHandler(
        log_dir / 'tabauno_agent.log',
        maxBytes=1_000_000,
        backupCount=5,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def _request(config, method, path, body=None):
    base = str(config['mytab_url']).rstrip('/')
    data = None if body is None else json.dumps(body).encode('utf-8')
    request = urllib.request.Request(
        f'{base}{path}',
        data=data,
        headers={
            'Authorization': f"Bearer {config['agent_token']}",
            'Accept': 'application/json',
            'User-Agent': 'myTaba-TabaUnoAgent/1.0',
            **({'Content-Type': 'application/json'} if data is not None else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            if response.status == 204 or not raw:
                return response.status, None
            return response.status, json.loads(raw.decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise TabaUnoError(f'{method} {path} -> {exc.code}: {detail}') from exc


def _request_bytes(config, path) -> bytes:
    base = str(config['mytab_url']).rstrip('/')
    request = urllib.request.Request(
        f'{base}{path}',
        headers={
            'Authorization': f"Bearer {config['agent_token']}",
            'Accept': 'application/vnd.ms-excel, application/octet-stream',
            'User-Agent': 'myTaba-TabaUnoAgent/1.0',
        },
        method='GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            if not raw:
                raise TabaUnoError(f'GET {path} -> file vuoto')
            return raw
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise TabaUnoError(f'GET {path} -> {exc.code}: {detail}') from exc


def write_ordine_logista(path: Path, content: bytes) -> dict:
    """Scrive Ordine_Logista.xls in modo atomico e verifica che il file esista con la size attesa."""
    if not content:
        raise TabaUnoError('File Ordine_Logista.xls vuoto: generazione non riuscita.')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    expected = len(content)
    try:
        tmp.write_bytes(content)
        os.replace(tmp, path)
    except PermissionError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise TabaUnoError(
            f'Impossibile scrivere {path}: file bloccato (chiudi Excel/Ordine_Logista.xls).'
        ) from exc
    except OSError as exc:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise TabaUnoError(f'Impossibile scrivere {path}: {exc}') from exc

    if not path.is_file():
        raise TabaUnoError(f'Deposito fallito: {path} non trovato dopo la scrittura.')
    actual = path.stat().st_size
    if actual != expected:
        raise TabaUnoError(
            f'Deposito incompleto su {path}: attesi {expected} byte, trovati {actual}.'
        )
    return {
        'ok': True,
        'verificato': True,
        'path': str(path),
        'bytes': actual,
        'messaggio': f'Ordine_Logista.xls generato correttamente su {path} ({actual} byte)',
    }


def _deposita_ordine_logista(config, request_id) -> dict:
    content = _request_bytes(config, f'/api/tabauno/agent/ordine-logista/{request_id}/')
    return write_ordine_logista(ordine_logista_path(config), content)


def _extract_request(config, payload):
    tipo = str(payload.get('tipo') or 'chiusura')
    day = payload.get('data')
    if tipo == 'chiusura':
        return extract_closure(
            config['tabauno_db'],
            day,
            storico_path=config.get('storico_db') or None,
            gratta=payload.get('gratta') or config.get('gratta') or 'B',
            snapshot=False,
        )
    if tipo == 'preordine_gratta':
        if not config.get('magx_db'):
            raise TabaUnoError('Config: manca magx_db.')
        return extract_gratta_data(
            config['tabauno_db'],
            config.get('storico_db') or None,
            config.get('magx_db'),
            day,
        )
    if tipo == 'preordine_tabacchi':
        if not config.get('magx_db'):
            raise TabaUnoError('Config: manca magx_db.')
        return extract_tabacchi_data(
            config['tabauno_db'],
            config.get('storico_db') or None,
            config.get('magx_db'),
            day,
        )
    if tipo == 'deposita_ordine_logista':
        return _deposita_ordine_logista(config, payload.get('id'))
    raise TabaUnoError(f'Tipo richiesta sconosciuto: {tipo}')


def poll_once(config, logger) -> None:
    status, payload = _request(config, 'GET', '/api/tabauno/agent/next/')
    if status == 204 or not payload:
        logger.info('contatto ok, nessuna richiesta')
        return
    request_id = payload.get('id')
    day = payload.get('data')
    tipo = payload.get('tipo') or 'chiusura'
    started = time.perf_counter()
    logger.info('richiesta id=%s tipo=%s data=%s', request_id, tipo, day)
    try:
        extracted = _extract_request(config, payload)
    except TabaUnoError as exc:
        logger.info('lettura fallita id=%s tipo=%s data=%s errore=%s', request_id, tipo, day, exc)
        _request(config, 'POST', f'/api/tabauno/agent/result/{request_id}/', {
            'ok': False,
            'errore': str(exc),
        })
        return
    elapsed = time.perf_counter() - started
    if tipo == 'preordine_gratta':
        logger.info(
            'lettura id=%s tipo=%s data=%s durata=%.3fs giochi=%s',
            request_id, tipo, day, elapsed, len(extracted.get('giochi') or []),
        )
    elif tipo == 'preordine_tabacchi':
        logger.info(
            'lettura id=%s tipo=%s data=%s durata=%.3fs articoli=%s',
            request_id, tipo, day, elapsed, len(extracted.get('articoli') or []),
        )
    elif tipo == 'deposita_ordine_logista':
        logger.info(
            'deposito id=%s durata=%.3fs path=%s bytes=%s',
            request_id, elapsed, extracted.get('path'), extracted.get('bytes'),
        )
    else:
        logger.info(
            'lettura id=%s data=%s durata=%.3fs totale=%s pagamenti=%s',
            request_id,
            day,
            elapsed,
            extracted.get('totale', {}).get('saldo'),
            (extracted.get('pagamenti') or {}).get('totale'),
        )
    _request(config, 'POST', f'/api/tabauno/agent/result/{request_id}/', {
        'ok': True,
        'payload': extracted,
    })


def run_agent(config_path) -> None:
    config = load_config(config_path)
    logger = _logger(config)
    interval = max(5, int(config.get('poll_seconds') or 10))
    failures = 0
    logger.info('agente avviato, poll=%ss path_ordine=%s', interval, ordine_logista_path(config))
    while True:
        try:
            poll_once(config, logger)
            failures = 0
            time.sleep(interval)
        except TabaUnoError as exc:
            logger.warning('rete: %s', exc)
            delay = _BACKOFF[min(failures, len(_BACKOFF) - 1)]
            failures += 1
            time.sleep(delay)
        except Exception:
            logger.exception('errore imprevisto')
            delay = _BACKOFF[min(failures, len(_BACKOFF) - 1)]
            failures += 1
            time.sleep(delay)
