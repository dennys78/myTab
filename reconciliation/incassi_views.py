"""Incassi parziali per la dashboard (utente autenticato)."""

from __future__ import annotations

from django.http import JsonResponse

from .company_scope import bind_company
from .incassi_parziali import ParzialiError, leggi_parziali
from .tabauno_portal import agent_is_online
from .views import require_auth


@require_auth
def api_incassi_parziali(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not agent_is_online(company):
        return JsonResponse({
            'status': 'error',
            'error': 'PC negozio offline. Avvia TabaUnoAgent e riprova.',
            'agent_online': False,
        }, status=409)
    try:
        dati = leggi_parziali(company, user=request.user)
    except ParzialiError as exc:
        status = 409 if exc.status == 409 else 503
        return JsonResponse({
            'status': 'error',
            'error': exc.messaggio,
            'agent_online': agent_is_online(company),
        }, status=status)
    return JsonResponse({
        'status': 'success',
        'agent_online': True,
        **dati,
    })
