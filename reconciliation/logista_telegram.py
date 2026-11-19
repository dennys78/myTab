"""Notifiche Telegram dei job Logista sul bot di myTaba, con esito di ogni tentativo (mai il token)."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .models import AppSetting

logger = logging.getLogger(__name__)

TIMEOUT = 30


def _chat_ids_env() -> list[str]:
    raw = os.environ.get('TELEGRAM_LOGISTA_CHAT_IDS', '')
    return [part.strip() for part in raw.split(',') if part.strip()]


def canale(company) -> dict:
    """Token e chat: stesse regole del bot (env, poi impostazione azienda, poi qualsiasi azienda)."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    fonte_token = 'env TELEGRAM_BOT_TOKEN' if token else ''
    if not token and company is not None:
        row = AppSetting.objects.filter(company=company, key='telegram_bot_token').exclude(value='').first()
        if row:
            token, fonte_token = row.value.strip(), f'impostazioni azienda «{company}»'
    if not token:
        row = AppSetting.objects.filter(key='telegram_bot_token').exclude(value='').select_related('company').first()
        if row:
            token, fonte_token = row.value.strip(), f'impostazioni azienda «{row.company}»'

    chat_ids = _chat_ids_env()
    fonte_chat = 'env TELEGRAM_LOGISTA_CHAT_IDS' if chat_ids else ''
    if not chat_ids and company is not None:
        from .user_notifications import telegram_chat_ids_for_company

        chat_ids = telegram_chat_ids_for_company(company)
        fonte_chat = f'operatori con notifiche attive di «{company}»'
    return {'token': token, 'fonte_token': fonte_token, 'chat_ids': chat_ids, 'fonte_chat': fonte_chat}


def _chiama(token: str, metodo: str, data: bytes, content_type: str) -> tuple[bool, int | None, str]:
    richiesta = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/{metodo}',
        data=data,
        headers={'Content-Type': content_type},
        method='POST',
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=TIMEOUT) as response:
            body = response.read()
            status = getattr(response, 'status', 200)
    except urllib.error.HTTPError as exc:
        try:
            descrizione = json.loads(exc.read().decode('utf-8', errors='replace')).get('description') or ''
        except (ValueError, OSError, AttributeError):
            descrizione = ''
        return False, exc.code, descrizione or exc.reason or 'errore HTTP'
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        motivo = getattr(exc, 'reason', None)
        return False, None, f'{type(exc).__name__}: {type(motivo).__name__ if motivo else "rete"}'
    try:
        ok = bool(json.loads(body or b'{}').get('ok', status == 200))
    except (ValueError, AttributeError):
        ok = status == 200
    return ok and status == 200, status, '' if ok else 'risposta ok=false'


def invia_messaggio(token: str, chat_id: str, testo: str):
    data = urllib.parse.urlencode({'chat_id': chat_id, 'text': testo}).encode('utf-8')
    return _chiama(token, 'sendMessage', data, 'application/x-www-form-urlencoded')


def invia_foto(token: str, chat_id: str, jpeg: bytes, caption: str = ''):
    boundary = f'----myTaba{uuid.uuid4().hex}'
    campi = {'chat_id': str(chat_id)}
    if caption:
        campi['caption'] = caption
    parti = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valore}\r\n'.encode('utf-8')
        for nome, valore in campi.items()
    ]
    parti.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="logista.jpg"\r\n'
        'Content-Type: image/jpeg\r\n\r\n'.encode('utf-8')
    )
    parti.extend([jpeg, f'\r\n--{boundary}--\r\n'.encode('utf-8')])
    return _chiama(token, 'sendPhoto', b''.join(parti), f'multipart/form-data; boundary={boundary}')


def notifica(company, testo: str, foto: bytes = b'', etichetta: str = 'Logista', caption_max: int = 1024) -> dict:
    """Invia testo (e foto) a tutte le chat del canale. Ritorna l'esito dettagliato, senza token."""
    info = canale(company)
    esito = {
        'ok': False,
        'fonte_token': info['fonte_token'],
        'fonte_chat': info['fonte_chat'],
        'chat': len(info['chat_ids']),
        'tentativi': [],
    }
    if not info['token']:
        esito['motivo'] = 'Token bot Telegram assente (né TELEGRAM_BOT_TOKEN né impostazioni).'
        logger.warning('notifica Telegram %s: %s', etichetta, esito['motivo'])
        return esito
    if not info['chat_ids']:
        esito['motivo'] = f"Nessuna chat Telegram ({info['fonte_chat'] or 'nessuna azienda'})."
        logger.warning('notifica Telegram %s: %s', etichetta, esito['motivo'])
        return esito

    def registra(chat_id, metodo, risultato):
        ok, http, dettaglio = risultato
        esito['tentativi'].append({'chat': chat_id, 'metodo': metodo, 'ok': ok, 'http': http, 'dettaglio': dettaglio})
        livello = logging.INFO if ok else logging.WARNING
        logger.log(
            livello, 'notifica Telegram %s chat %s %s: %s HTTP %s %s',
            etichetta, chat_id, metodo, 'OK' if ok else 'FALLITA', http if http is not None else '-', dettaglio,
        )
        return ok

    consegnate = 0
    for chat_id in info['chat_ids']:
        if foto and len(testo) <= caption_max:
            ok = registra(chat_id, 'sendPhoto', invia_foto(info['token'], chat_id, foto, testo))
            if not ok:
                ok = registra(chat_id, 'sendMessage', invia_messaggio(info['token'], chat_id, testo))
        else:
            ok = registra(chat_id, 'sendMessage', invia_messaggio(info['token'], chat_id, testo))
            if ok and foto:
                registra(chat_id, 'sendPhoto', invia_foto(info['token'], chat_id, foto))
        consegnate += int(ok)
    esito['consegnate'] = consegnate
    esito['ok'] = consegnate > 0
    if not esito['ok']:
        esito['motivo'] = 'Telegram ha rifiutato tutti i tentativi.'
    return esito
