"""Preordine gratta: il portale chiede la lettura, myTaba calcola, n8n riceve il JSON."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import socket
import urllib.error
import urllib.request
from datetime import timedelta
from decimal import Decimal

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .company_scope import bind_company
from .gratta_preordine import (
    GIORNI_VALIDI,
    _decimal,
    _money,
    aggio_stimato,
    calcola_righe,
    codici_esclusi_da_testo,
    corpo_n8n,
    giorni_alla_consegna,
    numero_json,
    proposta_pacchi,
    sotto_minimo,
)
from .models import AppSetting, GrattaPreordine, GrattaPreordineRiga, TabaUnoRequest
from .tabauno_portal import _bearer, agent_is_online, expire_requests
from .views import require_auth

N8N_TIMEOUT = 15
STATI_MODIFICABILI = {
    GrattaPreordine.BOZZA,
    GrattaPreordine.ANNULLATO,
    GrattaPreordine.ERRORE,
}
STATI_INVII = {GrattaPreordine.BOZZA, GrattaPreordine.ERRORE}
TRANSIZIONI = {
    GrattaPreordine.INVIATO_N8N: {
        GrattaPreordine.INVIATO_N8N,
        GrattaPreordine.CARRELLO_PRONTO,
        GrattaPreordine.CONFERMATO,
        GrattaPreordine.INVIATO_PORTALE,
        GrattaPreordine.ANNULLATO,
        GrattaPreordine.ERRORE,
    },
    GrattaPreordine.CARRELLO_PRONTO: {
        GrattaPreordine.CARRELLO_PRONTO,
        GrattaPreordine.CONFERMATO,
        GrattaPreordine.INVIATO_PORTALE,
        GrattaPreordine.ANNULLATO,
        GrattaPreordine.ERRORE,
    },
    GrattaPreordine.CONFERMATO: {
        GrattaPreordine.CONFERMATO,
        GrattaPreordine.INVIATO_PORTALE,
        GrattaPreordine.ANNULLATO,
        GrattaPreordine.ERRORE,
    },
    GrattaPreordine.INVIATO_PORTALE: {
        GrattaPreordine.INVIATO_PORTALE,
        GrattaPreordine.ANNULLATO,
        GrattaPreordine.ERRORE,
    },
}


def _body(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _company(request):
    company, err = bind_company(request)
    return company, err


def _codici_esclusi(company):
    setting = AppSetting.objects.filter(company=company, key='gratta_codici_esclusi').first()
    return codici_esclusi_da_testo(setting.value if setting else None)


def _giorni(value, default=7):
    if value is None or value == '':
        giorni = default
    else:
        try:
            giorni = int(value)
        except (TypeError, ValueError):
            return None
    if giorni not in GIORNI_VALIDI:
        return None
    return giorni


def _consegna(value, default):
    if not value:
        return default
    day = parse_date(str(value))
    return day


def _ultimo(preordine):
    payload = (preordine.request.payload or {}) if preordine.request_id else {}
    return payload.get('ultimo_giorno_chiuso')


def _letto_alle(preordine):
    payload = (preordine.request.payload or {}) if preordine.request_id else {}
    return payload.get('letto_alle') or ''


def _distanza(preordine):
    ultimo = _ultimo(preordine)
    if not ultimo:
        return 0
    return giorni_alla_consegna(timezone.localdate(), ultimo, preordine.data_consegna)


def _applica_proposta(riga, giorni, distanza, pacchi_forzati=None, toccata=False):
    proposta = proposta_pacchi(riga.media, riga.giacenza, riga.biglietti_pacco, giorni, distanza)
    proposti = 0 if riga.escluso else proposta['pacchi']
    riga.pacchi_proposti = proposti
    if toccata:
        riga.pacchi = max(0, int(pacchi_forzati))
    elif not riga.corretto_a_mano:
        riga.pacchi = proposti
    riga.corretto_a_mano = int(riga.pacchi) != int(proposti)
    riga.importo = _money(int(riga.pacchi) * _decimal(riga.valore_pacco))


def _salva_totali(preordine):
    totale = sum((_decimal(riga.importo) for riga in preordine.righe.all()), Decimal('0'))
    preordine.totale = _money(totale)
    preordine.save()


def _riga_json(riga, distanza, giorni):
    proposta = proposta_pacchi(riga.media, riga.giacenza, riga.biglietti_pacco, giorni, distanza)
    coperti = None if riga.media == 0 else float(proposta['alla_consegna'] / _decimal(riga.media))
    if int(riga.pacchi) > 0:
        gruppo = 'ordinare'
    elif riga.escluso:
        gruppo = 'occhio' if coperti is not None and coperti < (giorni + 3) else 'coperti'
    else:
        gruppo = proposta['gruppo']
    return {
        'id_articolo': riga.id_articolo,
        'codice': riga.codice,
        'descrizione': riga.descrizione,
        'prezzo': numero_json(riga.prezzo),
        'biglietti_pacco': numero_json(riga.biglietti_pacco),
        'valore_pacco': numero_json(riga.valore_pacco),
        'giacenza': numero_json(riga.giacenza),
        'media': float(riga.media),
        'giorni_esauriti': riga.giorni_esauriti,
        'settimane': riga.settimane or [0, 0, 0, 0],
        'pacchi_proposti': riga.pacchi_proposti,
        'pacchi': riga.pacchi,
        'corretto_a_mano': riga.corretto_a_mano,
        'importo': numero_json(riga.importo),
        'escluso': riga.escluso,
        'giorni_coperti': None if coperti is None else round(coperti, 2),
        'gruppo': gruppo,
    }


def _preordine_json(preordine, company):
    distanza = _distanza(preordine)
    righe = [_riga_json(riga, distanza, preordine.giorni_copertura) for riga in preordine.righe.all()]
    totale = _decimal(preordine.totale)
    modificabile = preordine.stato in STATI_MODIFICABILI
    return {
        'id': preordine.id,
        'stato': preordine.stato,
        'messaggio_stato': preordine.messaggio_stato,
        'giorni_copertura': preordine.giorni_copertura,
        'data_consegna': preordine.data_consegna.isoformat(),
        'giorni_alla_consegna': distanza,
        'ultimo_giorno_chiuso': _ultimo(preordine),
        'letto_alle': _letto_alle(preordine),
        'totale': numero_json(totale),
        'aggio_stimato': numero_json(aggio_stimato(totale)),
        'sotto_minimo': sotto_minimo(totale),
        'modificabile': modificabile,
        'agent_online': agent_is_online(company),
        'request_id': preordine.request_id,
        'righe': righe,
        'aggiornato_il': timezone.localtime(preordine.aggiornato_il).isoformat(timespec='seconds'),
    }


def _crea_righe(preordine, dati, company):
    calcolate = calcola_righe(
        dati,
        timezone.localdate(),
        giorni_copertura=preordine.giorni_copertura,
        data_consegna=preordine.data_consegna,
        codici_esclusi=_codici_esclusi(company),
    )
    GrattaPreordineRiga.objects.bulk_create([
        GrattaPreordineRiga(
            preordine=preordine,
            id_articolo=riga['id_articolo'],
            codice=riga['codice'],
            descrizione=riga['descrizione'],
            prezzo=riga['prezzo'],
            biglietti_pacco=riga['biglietti_pacco'],
            valore_pacco=riga['valore_pacco'],
            giacenza=riga['giacenza'],
            media=riga['media'],
            giorni_esauriti=riga['giorni_esauriti'],
            settimane=riga['settimane'],
            pacchi_proposti=riga['pacchi_proposti'],
            pacchi=riga['pacchi'],
            importo=riga['importo'],
            escluso=riga['escluso'],
        )
        for riga in calcolate
    ])
    _salva_totali(preordine)


def _callback_url(request, preordine_id):
    return request.build_absolute_uri(f'/api/gratta/preordini/{preordine_id}/stato/')


def _corpo(request, preordine, token=None):
    return corpo_n8n(
        preordine,
        list(preordine.righe.all()),
        azienda_id=preordine.company_id,
        azienda_nome=preordine.company.denominazione,
        creato_da=preordine.creato_da.username if preordine.creato_da_id else '',
        data_ordine=timezone.localdate(),
        letto_alle=_letto_alle(preordine),
        callback_url=_callback_url(request, preordine.id),
        callback_token=token,
    )


@require_auth
def api_gratta_preordini(request):
    company, err = _company(request)
    if err:
        return err
    if request.method == 'GET':
        rows = GrattaPreordine.objects.filter(company=company).order_by('-creato_il', '-id')[:30]
        return JsonResponse({'status': 'success', 'preordini': [
            {
                'id': row.id,
                'stato': row.stato,
                'data_consegna': row.data_consegna.isoformat(),
                'giorni_copertura': row.giorni_copertura,
                'totale': numero_json(row.totale),
                'creato_il': timezone.localtime(row.creato_il).isoformat(timespec='seconds'),
                'messaggio_stato': row.messaggio_stato,
            }
            for row in rows
        ], 'agent_online': agent_is_online(company)})
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa GET o POST'}, status=405)
    expire_requests()
    existing = TabaUnoRequest.objects.filter(
        company=company,
        tipo=TabaUnoRequest.TIPO_PREORDINE_GRATTA,
        status__in=(TabaUnoRequest.PENDING, TabaUnoRequest.PROCESSING),
    ).order_by('created_at', 'id').first()
    if existing:
        return JsonResponse({
            'status': 'success',
            'created': False,
            'id': existing.id,
            'request_status': existing.status,
            'agent_online': agent_is_online(company),
        })
    row = TabaUnoRequest.objects.create(
        company=company,
        date=timezone.localdate(),
        tipo=TabaUnoRequest.TIPO_PREORDINE_GRATTA,
        parametri={},
        requested_by=request.user,
    )
    return JsonResponse({
        'status': 'success',
        'created': True,
        'id': row.id,
        'request_status': row.status,
        'agent_online': agent_is_online(company),
    }, status=201)


@require_auth
def api_gratta_preordine_da_richiesta(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = _company(request)
    if err:
        return err
    data = _body(request)
    if data is None:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    lettura = TabaUnoRequest.objects.filter(
        id=request_id, company=company, tipo=TabaUnoRequest.TIPO_PREORDINE_GRATTA,
    ).first()
    if not lettura:
        return JsonResponse({'status': 'error', 'error': 'Richiesta non trovata.'}, status=404)
    if lettura.status != TabaUnoRequest.DONE or not isinstance(lettura.payload, dict):
        return JsonResponse({'status': 'error', 'error': 'La lettura TabaUno non è pronta.'}, status=409)
    giorni = _giorni(data.get('giorni_copertura'), 7)
    if giorni is None:
        return JsonResponse({'status': 'error', 'error': 'Giorni di copertura non validi.'}, status=400)
    consegna = _consegna(data.get('data_consegna'), timezone.localdate() + timedelta(days=1))
    if not consegna:
        return JsonResponse({'status': 'error', 'error': 'Data di consegna non valida.'}, status=400)
    esistente = GrattaPreordine.objects.filter(company=company, request=lettura).order_by('-id').first()
    if esistente:
        return JsonResponse({'status': 'success', 'created': False, 'preordine': _preordine_json(esistente, company)})
    preordine = GrattaPreordine.objects.create(
        company=company,
        creato_da=request.user,
        request=lettura,
        data_consegna=consegna,
        giorni_copertura=giorni,
    )
    _crea_righe(preordine, lettura.payload, company)
    preordine.refresh_from_db()
    return JsonResponse({'status': 'success', 'created': True, 'preordine': _preordine_json(preordine, company)}, status=201)


@require_auth
def api_gratta_preordine_detail(request, preordine_id):
    company, err = _company(request)
    if err:
        return err
    preordine = GrattaPreordine.objects.filter(id=preordine_id, company=company).first()
    if not preordine:
        return JsonResponse({'status': 'error', 'error': 'Preordine non trovato.'}, status=404)
    if request.method == 'GET':
        return JsonResponse({'status': 'success', 'preordine': _preordine_json(preordine, company)})
    if request.method != 'PATCH':
        return JsonResponse({'status': 'error', 'error': 'Usa GET o PATCH'}, status=405)
    if preordine.stato not in STATI_MODIFICABILI:
        return JsonResponse({'status': 'error', 'error': 'Ordine già inviato: non si può modificare.'}, status=409)
    data = _body(request)
    if data is None:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    if 'giorni_copertura' in data:
        giorni = _giorni(data.get('giorni_copertura'))
        if giorni is None:
            return JsonResponse({'status': 'error', 'error': 'Giorni di copertura non validi.'}, status=400)
        preordine.giorni_copertura = giorni
    if 'data_consegna' in data:
        consegna = parse_date(str(data.get('data_consegna') or ''))
        if not consegna:
            return JsonResponse({'status': 'error', 'error': 'Data di consegna non valida.'}, status=400)
        preordine.data_consegna = consegna
    if preordine.stato in {GrattaPreordine.ANNULLATO, GrattaPreordine.ERRORE}:
        preordine.stato = GrattaPreordine.BOZZA
        preordine.messaggio_stato = ''
    preordine.save()
    ultimo = _ultimo(preordine)
    if not ultimo:
        return JsonResponse({'status': 'error', 'error': 'Manca la data di chiusura letta da TabaUno.'}, status=409)
    distanza = giorni_alla_consegna(timezone.localdate(), ultimo, preordine.data_consegna)
    inviate = {}
    for item in data.get('righe') or []:
        if isinstance(item, dict) and item.get('codice') is not None:
            try:
                inviate[str(item['codice'])] = int(item.get('pacchi') or 0)
            except (TypeError, ValueError):
                return JsonResponse({'status': 'error', 'error': 'Pacchi non validi.'}, status=400)
    for riga in preordine.righe.all():
        if riga.codice in inviate:
            _applica_proposta(riga, preordine.giorni_copertura, distanza, inviate[riga.codice], True)
        else:
            _applica_proposta(riga, preordine.giorni_copertura, distanza)
        riga.save()
    _salva_totali(preordine)
    preordine.refresh_from_db()
    return JsonResponse({'status': 'success', 'preordine': _preordine_json(preordine, company)})


@require_auth
def api_gratta_preordine_json(request, preordine_id):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    company, err = _company(request)
    if err:
        return err
    preordine = GrattaPreordine.objects.filter(id=preordine_id, company=company).select_related('company', 'creato_da').first()
    if not preordine:
        return JsonResponse({'status': 'error', 'error': 'Preordine non trovato.'}, status=404)
    payload = _corpo(request, preordine, token=None)
    response = JsonResponse(payload)
    response['Content-Disposition'] = f'attachment; filename="ordine-gratta-{preordine.id}.json"'
    return response


def _n8n_config():
    url = os.environ.get('N8N_GRATTA_WEBHOOK_URL', '').strip()
    token = os.environ.get('N8N_GRATTA_TOKEN', '').strip()
    return url, token


def _posta_n8n(url, token, payload):
    raw = json.dumps(payload).encode('utf-8')
    richiesta = urllib.request.Request(
        url,
        data=raw,
        headers={
            'Content-Type': 'application/json',
            'x-api-key': token,
            'User-Agent': 'myTaba-Gratta/1.0',
        },
        method='POST',
    )
    with urllib.request.urlopen(richiesta, timeout=N8N_TIMEOUT) as response:
        response.read()


@require_auth
def api_gratta_preordine_invia(request, preordine_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = _company(request)
    if err:
        return err
    preordine = GrattaPreordine.objects.filter(id=preordine_id, company=company).select_related('company', 'creato_da', 'request').first()
    if not preordine:
        return JsonResponse({'status': 'error', 'error': 'Preordine non trovato.'}, status=404)
    if preordine.stato not in STATI_INVII:
        return JsonResponse({'status': 'error', 'error': 'Questo ordine non è in bozza.'}, status=409)
    if sotto_minimo(preordine.totale):
        return JsonResponse({
            'status': 'error',
            'error': 'Ordine sotto il minimo di 900 €.' if _decimal(preordine.totale) > 0 else 'Nessun pacco da ordinare.',
        }, status=400)
    url, token = _n8n_config()
    if not url or not token:
        return JsonResponse({'status': 'error', 'error': 'Webhook n8n non configurato.'}, status=503)
    chiaro = secrets.token_urlsafe(32)
    payload = _corpo(request, preordine, token=chiaro)
    try:
        _posta_n8n(url, token, payload)
    except urllib.error.HTTPError as exc:
        dettaglio = exc.read().decode('utf-8', errors='replace')[:300]
        preordine.stato = GrattaPreordine.ERRORE
        preordine.messaggio_stato = f'n8n ha risposto {exc.code}: {dettaglio}'.strip()
        preordine.payload_inviato = payload
        preordine.callback_token_hash = ''
        preordine.save()
        return JsonResponse({'status': 'error', 'error': preordine.messaggio_stato, 'preordine': _preordine_json(preordine, company)}, status=502)
    except (urllib.error.URLError, TimeoutError, socket.timeout):
        preordine.stato = GrattaPreordine.ERRORE
        preordine.messaggio_stato = 'n8n non ha risposto entro 15 secondi.'
        preordine.payload_inviato = payload
        preordine.callback_token_hash = ''
        preordine.save()
        return JsonResponse({'status': 'error', 'error': preordine.messaggio_stato, 'preordine': _preordine_json(preordine, company)}, status=504)
    preordine.stato = GrattaPreordine.INVIATO_N8N
    preordine.messaggio_stato = 'Inviato al bot. In attesa del carrello.'
    preordine.payload_inviato = payload
    preordine.callback_token_hash = _digest(chiaro)
    preordine.save()
    return JsonResponse({'status': 'success', 'preordine': _preordine_json(preordine, company)})


@csrf_exempt
def api_gratta_preordine_stato(request, preordine_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    preordine = GrattaPreordine.objects.filter(id=preordine_id).first()
    if not preordine or not preordine.callback_token_hash:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    presented = _bearer(request)
    if not presented or not hmac.compare_digest(_digest(presented), preordine.callback_token_hash):
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    data = _body(request)
    if data is None:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    stato = str(data.get('stato') or '')
    ammessi = TRANSIZIONI.get(preordine.stato, set())
    if stato not in ammessi:
        return JsonResponse({'status': 'error', 'error': 'Transizione di stato non valida.'}, status=409)
    preordine.stato = stato
    messaggio = str(data.get('messaggio') or '')[:2000]
    if data.get('totale_portale') is not None:
        try:
            portale = _money(data.get('totale_portale'))
            extra = f'Totale portale {numero_json(portale)} €.'
            messaggio = f'{messaggio} {extra}'.strip()
        except Exception:
            pass
    preordine.messaggio_stato = messaggio
    preordine.save(update_fields=['stato', 'messaggio_stato', 'aggiornato_il'])
    return JsonResponse({'status': 'success', 'stato': preordine.stato})
