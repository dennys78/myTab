"""Report giornaliero giacenze per n8n (testo HTML da inoltrare su Telegram dal bot ordini)."""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .giacenze_report import esegui_report
from .n8n_tabacchi_views import _attendi_lettura, _autorizzato, _company, _non_autorizzato


@csrf_exempt
def api_n8n_giacenze_report(request):
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

    status, body = esegui_report(company, attendi_lettura=_attendi_lettura)
    return JsonResponse(body, status=status)
