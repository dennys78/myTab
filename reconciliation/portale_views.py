"""API dashboard per prospetti portale Lotterie."""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils.dateparse import parse_date

from .company_scope import bind_company
from .models import PortaleGiornata
from .portale_giornata import leggi_portale, serializza_giornata, testo_telegram
from .portale_service import PortaleServiceError
from .views import require_auth


@require_auth
def api_portale_giornata(request):
    company, err = bind_company(request)
    if err:
        return err

    if request.method == 'GET':
        day = parse_date(str(request.GET.get('data') or ''))
        if not day:
            return JsonResponse({'status': 'error', 'error': 'Parametro data obbligatorio (YYYY-MM-DD).'}, status=400)
        row = PortaleGiornata.objects.filter(company=company, data=day).first()
        if not row:
            return JsonResponse({
                'status': 'success',
                'data': day.isoformat(),
                'contabile_lotto': None,
                'premi_lotterie': None,
                'letto_alle': '',
                'errore': '',
                'riconciliazione': None,
                'lotto': None,
                'premi_lotterie_vista': None,
                'assente': True,
            })
        return JsonResponse({'status': 'success', 'assente': False, **serializza_giornata(row)})

    if request.method == 'POST':
        try:
            body = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
        day = parse_date(str(body.get('data') or ''))
        if not day:
            return JsonResponse({'status': 'error', 'error': 'Campo data obbligatorio (YYYY-MM-DD).'}, status=400)
        try:
            row = leggi_portale(company, day)
        except PortaleServiceError as exc:
            return JsonResponse({'status': 'error', 'error': exc.messaggio}, status=503)
        except Exception as exc:
            return JsonResponse({'status': 'error', 'error': str(exc) or 'Lettura portale fallita'}, status=503)
        dati = serializza_giornata(row)
        return JsonResponse({'status': 'success', 'assente': False, **dati})

    return JsonResponse({'status': 'error', 'error': 'Usa GET o POST'}, status=405)
