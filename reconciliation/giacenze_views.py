"""Statistiche giacenze: lettura TabaUno + proiezione a una data futura."""

from __future__ import annotations

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .company_scope import bind_company
from .giacenze_stats import ETICHETTE_STATO, STATI, calcola_giacenze
from .models import AppSetting, TabaUnoRequest
from .tabacchi_preordine import DEFAULT_GIORNO_CONSEGNA, prossimo_giorno_consegna
from .tabacchi_views import accoda_lettura
from .tabauno_portal import agent_is_online, expire_requests
from .views import require_auth


def _company(request):
    return bind_company(request)


def _giorno_consegna_setting(company):
    setting = AppSetting.objects.filter(company=company, key='tabacchi_giorno_consegna').first()
    if not setting:
        return DEFAULT_GIORNO_CONSEGNA
    try:
        return int(setting.value) % 7
    except (TypeError, ValueError):
        return DEFAULT_GIORNO_CONSEGNA


def _ultima_lettura(company, request_id=None):
    expire_requests()
    qs = TabaUnoRequest.objects.filter(company=company, tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI)
    if request_id:
        return qs.filter(id=request_id).first()
    return (
        qs.filter(status=TabaUnoRequest.DONE)
        .exclude(payload=None)
        .order_by('-completed_at', '-id')
        .first()
    )


@require_auth
def api_giacenze_lettura(request):
    """Accoda la stessa lettura TabaUno usata da Ordine Tabacchi."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = _company(request)
    if err:
        return err
    if not agent_is_online(company):
        return JsonResponse({
            'status': 'error',
            'error': 'PC negozio offline. Avvia TabaUnoAgent e riprova.',
            'agent_online': False,
        }, status=409)
    row, created = accoda_lettura(company, request.user)
    return JsonResponse({
        'status': 'success',
        'created': created,
        'id': row.id,
        'request_status': row.status,
        'agent_online': True,
    }, status=201 if created else 200)


@require_auth
def api_giacenze_analisi(request):
    """Calcola le giacenze stimate alla data scelta a partire da una lettura TabaUno."""
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    company, err = _company(request)
    if err:
        return err
    request_id = request.GET.get('request_id')
    try:
        request_id = int(request_id) if request_id not in (None, '') else None
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'error': 'request_id non valido.'}, status=400)
    lettura = _ultima_lettura(company, request_id)
    if not lettura:
        return JsonResponse({
            'status': 'success',
            'pronta': False,
            'agent_online': agent_is_online(company),
            'analisi': None,
        })
    if lettura.status in (TabaUnoRequest.PENDING, TabaUnoRequest.PROCESSING):
        return JsonResponse({
            'status': 'success',
            'pronta': False,
            'request_id': lettura.id,
            'request_status': lettura.status,
            'agent_online': agent_is_online(company),
            'analisi': None,
        })
    if lettura.status != TabaUnoRequest.DONE or not isinstance(lettura.payload, dict):
        return JsonResponse({
            'status': 'error',
            'error': lettura.error or 'Lettura TabaUno non riuscita.',
            'request_id': lettura.id,
            'request_status': lettura.status,
            'agent_online': agent_is_online(company),
        }, status=409)

    oggi = timezone.localdate()
    giorno = _giorno_consegna_setting(company)
    consegna_default = prossimo_giorno_consegna(oggi, giorno)
    data_raw = request.GET.get('data') or ''
    data_proiezione = parse_date(str(data_raw)) if data_raw else consegna_default
    if data_raw and not data_proiezione:
        return JsonResponse({'status': 'error', 'error': 'Data non valida.'}, status=400)

    risultato = calcola_giacenze(
        lettura.payload,
        oggi,
        consegna=consegna_default,
        data_proiezione=data_proiezione,
        giorno_consegna=giorno,
    )
    payload = lettura.payload or {}
    return JsonResponse({
        'status': 'success',
        'pronta': True,
        'request_id': lettura.id,
        'agent_online': agent_is_online(company),
        'analisi': {
            **risultato,
            'ultimo_giorno_chiuso': payload.get('ultimo_giorno_chiuso'),
            'letto_alle': payload.get('letto_alle') or '',
            'etichette_stato': ETICHETTE_STATO,
            'stati': list(STATI),
            'consegna_default': consegna_default.isoformat(),
        },
    })
