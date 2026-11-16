"""Richieste di chiusura TabaUno: il portale accoda, l'agente sul PC legge il DB."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import timedelta

from django.db import connection, transaction
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .company_scope import bind_company
from .models import Company, TabaUnoAgent, TabaUnoRequest
from .views import require_admin, require_auth

import json

PENDING_TTL = timedelta(minutes=10)
PROCESSING_TTL = timedelta(minutes=5)
ONLINE_WINDOW = timedelta(seconds=60)
AGENT_SILENT = 'Agente non ha risposto'


def _bearer(request):
    header = request.headers.get('Authorization', '')
    if header.lower().startswith('bearer '):
        return header[7:].strip()
    return ''


def _digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def agent_for_token(token):
    if not token:
        return None
    agent = TabaUnoAgent.objects.select_related('company').filter(token_hash=_digest(token)).first()
    if agent:
        return agent
    expected = os.environ.get('TABAUNO_IMPORT_TOKEN', '').strip()
    if not expected or not hmac.compare_digest(expected, token):
        return None
    taken = TabaUnoAgent.objects.exclude(token_hash='').values_list('company_id', flat=True)
    free = list(Company.objects.exclude(id__in=list(taken)).order_by('id')[:2])
    if len(free) != 1:
        return None
    agent, _created = TabaUnoAgent.objects.get_or_create(company=free[0])
    return agent


def touch_agent(agent):
    agent.last_seen = timezone.now()
    agent.save(update_fields=['last_seen'])


def agent_is_online(company):
    agent = TabaUnoAgent.objects.filter(company=company).only('last_seen').first()
    if not agent or not agent.last_seen:
        return False
    return timezone.now() - agent.last_seen < ONLINE_WINDOW


def expire_requests(now=None):
    now = now or timezone.now()
    TabaUnoRequest.objects.filter(
        status=TabaUnoRequest.PENDING,
        created_at__lt=now - PENDING_TTL,
    ).update(status=TabaUnoRequest.EXPIRED, completed_at=now)
    TabaUnoRequest.objects.filter(
        status=TabaUnoRequest.PROCESSING,
        picked_at__lt=now - PROCESSING_TTL,
    ).update(status=TabaUnoRequest.ERROR, error=AGENT_SILENT, completed_at=now)


def claim_next_request(company):
    """Prende una sola richiesta pending. Su PostgreSQL usa SKIP LOCKED; su SQLite un update condizionale."""
    expire_requests()
    now = timezone.now()
    with transaction.atomic():
        pending = TabaUnoRequest.objects.filter(
            company=company,
            status=TabaUnoRequest.PENDING,
        ).order_by('created_at', 'id')
        features = connection.features
        if features.has_select_for_update:
            lock = {}
            if features.has_select_for_update_skip_locked:
                lock['skip_locked'] = True
            request = pending.select_for_update(**lock).first()
            if request is None:
                return None
            request.status = TabaUnoRequest.PROCESSING
            request.picked_at = now
            request.save(update_fields=['status', 'picked_at'])
            return request
        candidate = pending.first()
        if candidate is None:
            return None
        updated = TabaUnoRequest.objects.filter(
            pk=candidate.pk,
            status=TabaUnoRequest.PENDING,
        ).update(status=TabaUnoRequest.PROCESSING, picked_at=now)
        if not updated:
            return None
        candidate.refresh_from_db()
        return candidate


def _request_body(row, company):
    return {
        'id': row.id,
        'status': row.status,
        'date': row.date.isoformat(),
        'gratta': row.gratta,
        'payload': row.payload,
        'error': row.error,
        'agent_online': agent_is_online(company),
    }


@require_auth
def api_tabauno_status(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    return JsonResponse({'status': 'success', 'agent_online': agent_is_online(company)})


@require_auth
def api_tabauno_requests(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    day = parse_date(str(data.get('date') or ''))
    if not day:
        return JsonResponse({'status': 'error', 'error': 'Data non valida, usa YYYY-MM-DD.'}, status=400)
    if day > timezone.localdate():
        return JsonResponse({'status': 'error', 'error': 'La data non può essere nel futuro.'}, status=400)
    gratta = str(data.get('gratta') or 'B').strip().upper()
    if gratta not in {'A', 'B'}:
        return JsonResponse({'status': 'error', 'error': 'Regola Gratta non valida.'}, status=400)
    expire_requests()
    existing = TabaUnoRequest.objects.filter(
        company=company,
        date=day,
        status__in=(TabaUnoRequest.PENDING, TabaUnoRequest.PROCESSING),
    ).order_by('created_at', 'id').first()
    if existing:
        return JsonResponse({'status': 'success', 'created': False, **_request_body(existing, company)})
    row = TabaUnoRequest.objects.create(
        company=company,
        date=day,
        gratta=gratta,
        requested_by=request.user,
    )
    return JsonResponse({'status': 'success', 'created': True, **_request_body(row, company)}, status=201)


@require_auth
def api_tabauno_request_detail(request, request_id):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    expire_requests()
    row = TabaUnoRequest.objects.filter(id=request_id, company=company).first()
    if not row:
        return JsonResponse({'status': 'error', 'error': 'Richiesta non trovata.'}, status=404)
    row.refresh_from_db()
    return JsonResponse({'status': 'success', **_request_body(row, company)})


@require_admin
def api_tabauno_rotate_token(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    raw = secrets.token_urlsafe(32)
    agent, _created = TabaUnoAgent.objects.get_or_create(company=company)
    agent.token_hash = _digest(raw)
    agent.save(update_fields=['token_hash', 'updated_at'])
    return JsonResponse({'status': 'success', 'token': raw})


@csrf_exempt
def api_tabauno_agent_next(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    agent = agent_for_token(_bearer(request))
    if not agent:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    touch_agent(agent)
    row = claim_next_request(agent.company)
    if row is None:
        return HttpResponse(status=204)
    return JsonResponse({'id': row.id, 'data': row.date.isoformat(), 'gratta': row.gratta})


@csrf_exempt
def api_tabauno_agent_result(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    agent = agent_for_token(_bearer(request))
    if not agent:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    touch_agent(agent)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    row = TabaUnoRequest.objects.filter(id=request_id, company=agent.company).first()
    if not row or row.status != TabaUnoRequest.PROCESSING:
        return JsonResponse({'status': 'error', 'error': 'Richiesta non in lettura.'}, status=409)
    if data.get('ok'):
        payload = data.get('payload')
        if not isinstance(payload, dict):
            return JsonResponse({'status': 'error', 'error': 'Payload mancante.'}, status=400)
        row.payload = payload
        row.error = ''
        row.status = TabaUnoRequest.DONE
    else:
        row.status = TabaUnoRequest.ERROR
        row.error = str(data.get('errore') or 'Errore lettura TabaUno')[:2000]
    row.completed_at = timezone.now()
    row.save(update_fields=['payload', 'error', 'status', 'completed_at'])
    return JsonResponse({'status': 'success', 'id': row.id})
