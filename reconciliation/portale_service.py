"""Client HTTP del servizio portale Lotterie sul Mac mini (porta 3500)."""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_URL = 'http://host.docker.internal:3500'
TIMEOUT = 60
OCCUPATO_ATTESA = 5
OCCUPATO_TENTATIVI = 3


class PortaleServiceError(RuntimeError):
    def __init__(self, messaggio: str, *, status: int | None = None):
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.status = status


def portale_config():
    url = (os.environ.get('PORTALE_SERVICE_URL') or DEFAULT_URL).strip().rstrip('/')
    key = (os.environ.get('LOGISTA_SERVICE_KEY') or '').strip()
    return url, key


def portale_configurato() -> bool:
    return bool(portale_config()[1])


def _messaggio_http(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode('utf-8', errors='replace') or '{}')
    except (ValueError, OSError):
        body = {}
    dettaglio = str(body.get('errore') or '').strip() if isinstance(body, dict) else ''
    if exc.code == 409:
        return 'Servizio portale occupato (ordine/carrello in corso).'
    if exc.code in (401, 403):
        return 'Servizio portale: chiave non valida.'
    if exc.code == 502:
        return dettaglio or 'Servizio portale: lettura prospetto fallita.'
    return f'Servizio portale ha risposto {exc.code}' + (f': {dettaglio}' if dettaglio else '.')


def _get(percorso: str, timeout: int = TIMEOUT) -> dict:
    url, key = portale_config()
    if not key:
        raise PortaleServiceError('Servizio portale non configurato (manca LOGISTA_SERVICE_KEY).')
    richiesta = urllib.request.Request(
        f'{url}{percorso}',
        headers={
            'Accept': 'application/json',
            'x-api-key': key,
            'User-Agent': 'myTaba-Portale/1.0',
        },
        method='GET',
    )
    ultimo_409 = None
    for tentativo in range(1, OCCUPATO_TENTATIVI + 1):
        try:
            with urllib.request.urlopen(richiesta, timeout=timeout) as response:
                body = response.read().decode('utf-8', errors='replace')
        except urllib.error.HTTPError as exc:
            if exc.code == 409 and tentativo < OCCUPATO_TENTATIVI:
                ultimo_409 = exc
                logger.info('portale occupato, ritento tra %ss (%s/%s)', OCCUPATO_ATTESA, tentativo, OCCUPATO_TENTATIVI)
                time.sleep(OCCUPATO_ATTESA)
                continue
            raise PortaleServiceError(_messaggio_http(exc), status=exc.code) from exc
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise PortaleServiceError(f'Servizio portale: tempo scaduto ({timeout} s).') from exc
            raise PortaleServiceError(
                'Servizio portale non raggiungibile sul Mac mini (porta 3500).',
            ) from exc
        except (TimeoutError, OSError) as exc:
            raise PortaleServiceError(f'Servizio portale: tempo scaduto ({timeout} s).') from exc
        try:
            data = json.loads(body or '{}')
        except ValueError as exc:
            raise PortaleServiceError('Servizio portale: risposta non valida.') from exc
        if not isinstance(data, dict):
            raise PortaleServiceError('Servizio portale: risposta non valida.')
        return data
    raise PortaleServiceError(_messaggio_http(ultimo_409), status=409)


def get_contabile_lotto(data_iso: str) -> dict:
    return _get(f'/lotto/contabile?data={data_iso}')


def get_premi_pagati(data_iso: str) -> dict:
    return _get(f'/lotterie/premi-pagati?data={data_iso}')
