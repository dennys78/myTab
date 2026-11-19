"""Ordine tabacchi da n8n/Telegram: lettura TabaUno → preordine → caricamento proposta Logista."""

from __future__ import annotations

import hmac
import json
import os
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .logista_service import (
    crea_job,
    job_attivo,
    job_json,
    logista_configurato,
    riepilogo_preordine,
    scadi_job_bloccati,
)
from .models import Company, LogistaInvioJob, TabaUnoAgent, TabaUnoRequest
from .tabacchi_views import accoda_lettura, crea_preordine_da_lettura
from .tabauno_portal import agent_is_online, expire_requests

# Deve restare sotto il --timeout 300 di gunicorn.
LETTURA_TIMEOUT = 240
LETTURA_POLL = 2
AGENTE_IRRAGGIUNGIBILE = 'Agente TabaUno non raggiungibile'


def _token_atteso() -> str:
    return (
        os.environ.get('N8N_TABACCHI_TOKEN', '').strip()
        or os.environ.get('N8N_GRATTA_TOKEN', '').strip()
    )


def _autorizzato(request) -> bool:
    atteso = _token_atteso()
    presentato = (request.headers.get('X-N8N-Token') or '').strip()
    if not atteso or not presentato:
        return False
    return hmac.compare_digest(atteso.encode('utf-8'), presentato.encode('utf-8'))


def _non_autorizzato():
    return JsonResponse({'errore': 'Non autorizzato'}, status=401)


def _company(company_id):
    if company_id:
        return Company.objects.filter(id=company_id).first()
    ids = list(TabaUnoAgent.objects.values_list('company_id', flat=True)[:2])
    if len(ids) == 1:
        return Company.objects.filter(id=ids[0]).first()
    return None


def _attendi_lettura(row: TabaUnoRequest) -> TabaUnoRequest | None:
    scadenza = time.monotonic() + LETTURA_TIMEOUT
    while True:
        expire_requests()
        row.refresh_from_db()
        if row.status == TabaUnoRequest.DONE:
            return row if isinstance(row.payload, dict) else None
        if row.status in (TabaUnoRequest.ERROR, TabaUnoRequest.EXPIRED):
            return None
        if time.monotonic() >= scadenza:
            return None
        time.sleep(LETTURA_POLL)


@csrf_exempt
def api_n8n_tabacchi_logista_avvia(request):
    if request.method != 'POST':
        return JsonResponse({'errore': 'Usa POST'}, status=405)
    if not _autorizzato(request):
        return _non_autorizzato()
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'errore': 'JSON non valido'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({'errore': 'JSON non valido'}, status=400)
    company = _company(data.get('company_id'))
    if not company:
        return JsonResponse({'errore': 'Azienda non determinabile: indica company_id.'}, status=400)
    if not logista_configurato():
        return JsonResponse({'errore': 'Servizio Logista non configurato.'}, status=503)
    scadi_job_bloccati(company)
    attivo = job_attivo(company)
    if attivo:
        return JsonResponse({'errore': 'C’è già un job Logista in corso.', 'job_id': attivo.id}, status=409)
    if not agent_is_online(company):
        return JsonResponse({'errore': AGENTE_IRRAGGIUNGIBILE}, status=503)

    lettura, _creata = accoda_lettura(company, None)
    lettura = _attendi_lettura(lettura)
    if lettura is None:
        return JsonResponse({'errore': AGENTE_IRRAGGIUNGIBILE}, status=503)

    preordine = crea_preordine_da_lettura(company, lettura, None)
    job, rifiuto = crea_job(company, preordine, None, bool(data.get('svuota')), LogistaInvioJob.ORIGINE_TELEGRAM)
    if rifiuto:
        status, errore, attivo_id = rifiuto
        body = {'errore': errore, 'preordine_id': preordine.id}
        if attivo_id:
            body['job_id'] = attivo_id
        return JsonResponse(body, status=status)
    return JsonResponse({
        'job_id': job.id,
        'preordine_id': preordine.id,
        'righe': job.righe_inviate,
        **riepilogo_preordine(preordine),
    }, status=202)


@csrf_exempt
def api_n8n_tabacchi_logista_job(request, job_id):
    if request.method != 'GET':
        return JsonResponse({'errore': 'Usa GET'}, status=405)
    if not _autorizzato(request):
        return _non_autorizzato()
    job = LogistaInvioJob.objects.filter(id=job_id).select_related('company').first()
    if not job:
        return JsonResponse({'errore': 'Job non trovato.'}, status=404)
    scadi_job_bloccati(job.company)
    job.refresh_from_db()
    return JsonResponse({'status': 'success', 'job': job_json(job)})
