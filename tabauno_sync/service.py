"""Agente sul PC del negozio: legge TabaUno solo quando il portale lo chiede."""

from __future__ import annotations

import json
import logging
import logging.handlers
import time
import urllib.error
import urllib.request
from pathlib import Path

from .extract import TabaUnoError, extract_closure

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
    config.setdefault('gratta', 'B')
    config.setdefault('poll_seconds', 10)
    config.setdefault('log_dir', 'logs')
    return config


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


def poll_once(config, logger) -> None:
    status, payload = _request(config, 'GET', '/api/tabauno/agent/next/')
    if status == 204 or not payload:
        return
    request_id = payload.get('id')
    day = payload.get('data')
    gratta = payload.get('gratta') or config.get('gratta') or 'B'
    started = time.perf_counter()
    logger.info('richiesta id=%s data=%s', request_id, day)
    try:
        extracted = extract_closure(
            config['tabauno_db'],
            day,
            storico_path=config.get('storico_db') or None,
            gratta=gratta,
            snapshot=False,
        )
    except TabaUnoError as exc:
        logger.info('lettura fallita id=%s data=%s errore=%s', request_id, day, exc)
        _request(config, 'POST', f'/api/tabauno/agent/result/{request_id}/', {
            'ok': False,
            'errore': str(exc),
        })
        return
    elapsed = time.perf_counter() - started
    logger.info(
        'lettura id=%s data=%s durata=%.3fs totale=%s',
        request_id,
        day,
        elapsed,
        extracted.get('totale', {}).get('saldo'),
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
    logger.info('agente avviato, poll=%ss', interval)
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
