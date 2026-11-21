"""Incassi parziali per n8n (testo Telegram da inoltrare)."""

from __future__ import annotations

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .incassi_parziali import (
    ParzialiError,
    leggi_parziali,
    messaggio_indisponibile,
    testo_telegram,
)
from .n8n_tabacchi_views import _autorizzato, _company, _non_autorizzato


@csrf_exempt
def api_n8n_cassa_parziali(request):
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

    try:
        dati = leggi_parziali(company)
    except ParzialiError as exc:
        messaggi = messaggio_indisponibile(exc.messaggio)
        return JsonResponse(
            {'errore': exc.messaggio, 'messaggi': messaggi, 'testo': messaggi[0]},
            status=503,
        )

    testo = testo_telegram(dati)
    return JsonResponse({**dati, 'testo': testo, 'messaggi': [testo]})
