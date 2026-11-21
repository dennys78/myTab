"""Prospetti portale Lotterie per n8n (testo Telegram da accodare al report)."""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt

from .n8n_tabacchi_views import _autorizzato, _company, _non_autorizzato
from .portale_giornata import leggi_portale, payload_n8n, testo_telegram
from .portale_service import PortaleServiceError


@csrf_exempt
def api_n8n_portale_giornata(request):
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

    raw = data.get('data')
    day = parse_date(str(raw)) if raw else timezone.localdate()
    if not day:
        return JsonResponse({'errore': 'Data non valida (YYYY-MM-DD).'}, status=400)

    try:
        row = leggi_portale(company, day)
    except PortaleServiceError as exc:
        testo = testo_telegram(None, motivo=exc.messaggio)
        return JsonResponse({
            'data': day.isoformat(),
            'lotto': None,
            'premi_lotterie': None,
            'riconciliazione': None,
            'errore': exc.messaggio,
            'testo': testo,
            'messaggi': [testo],
        })
    except Exception as exc:
        motivo = str(exc) or 'errore imprevisto'
        testo = testo_telegram(None, motivo=motivo)
        return JsonResponse({
            'data': day.isoformat(),
            'lotto': None,
            'premi_lotterie': None,
            'riconciliazione': None,
            'errore': motivo,
            'testo': testo,
            'messaggi': [testo],
        })

    out = payload_n8n(row)
    out['messaggi'] = [out['testo']]
    return JsonResponse(out)
