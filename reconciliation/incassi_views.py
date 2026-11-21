"""Incassi parziali per la dashboard (utente autenticato)."""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .company_scope import bind_company
from .incassi_parziali import ParzialiError, leggi_parziali
from .models import PortaleGiornata
from .portale_giornata import leggi_portale
from .tabauno_portal import agent_is_online
from .views import require_auth

logger = logging.getLogger(__name__)


def _lottomatica_da_portale(company, day):
    """Entrate Gioco dal Contabile portale (non cassagiorno). Non solleva."""
    try:
        row = leggi_portale(company, day)
    except Exception:
        logger.exception('incassi: lettura portale per Lottomatica fallita')
        row = PortaleGiornata.objects.filter(company=company, data=day).first()
        if not row:
            return {
                'disponibile': False,
                'errore': 'Portale Lotterie non raggiungibile',
                'importo': None,
                'uscite': None,
                'saldo': None,
                'richiesto_alle': '',
            }
    contabile = row.contabile_lotto if row and isinstance(row.contabile_lotto, dict) else None
    if not contabile:
        return {
            'disponibile': False,
            'errore': (row.errore if row and row.errore else 'Contabile Lotto non disponibile'),
            'importo': None,
            'uscite': None,
            'saldo': None,
            'richiesto_alle': '',
        }
    return {
        'disponibile': True,
        'errore': '',
        'importo': contabile.get('entrate'),
        'uscite': contabile.get('uscite'),
        'saldo': contabile.get('saldo'),
        'aggio': contabile.get('aggio'),
        'richiesto_alle': contabile.get('richiesto_alle') or '',
        'fonte': 'portale',
    }


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

    day = parse_date(str(dati.get('data') or '')) or timezone.localdate()
    lottomatica = _lottomatica_da_portale(company, day)
    return JsonResponse({
        'status': 'success',
        'agent_online': True,
        **dati,
        'lottomatica': lottomatica,
    })
