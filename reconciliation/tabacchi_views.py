"""Preordine tabacchi: il portale chiede la lettura, myTaba calcola, CSV/copia restano in pagina."""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .company_scope import bind_company
from .models import AppSetting, TabacchiPreordine, TabacchiPreordineRiga, TabaUnoRequest
from .tabacchi_preordine import (
    DEFAULT_GIORNO_CONSEGNA,
    FAMIGLIE,
    GIORNI_VALIDI,
    _decimal,
    _kg,
    _money,
    calcola_righe,
    giorni_alla_consegna,
    inizio_vendite,
    numero_json,
    proposta_unita,
    prossimo_giorno_consegna,
    totali_ordine,
    urgenza_data_fine,
)
from .tabauno_portal import agent_is_online, expire_requests
from .views import require_auth

STATI_MODIFICABILI = {
    TabacchiPreordine.BOZZA,
    TabacchiPreordine.ANNULLATO,
}


def _body(request):
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


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
    return parse_date(str(value))


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


def _applica_proposta(riga, giorni, distanza, unita_forzate=None, toccata=False):
    proposta = proposta_unita(riga.media, riga.giacenza, riga.pacchetti_per_unita, giorni, distanza)
    proposti = proposta['unita']
    riga.unita_proposte = proposti
    if toccata:
        riga.unita = max(0, int(unita_forzate))
    elif not riga.corretto_a_mano:
        riga.unita = proposti
    riga.corretto_a_mano = int(riga.unita) != int(proposti)
    pacchetti = int(riga.unita) * int(riga.pacchetti_per_unita)
    riga.importo = _money(pacchetti * _decimal(riga.prezzo))
    return proposta


def _salva_totali(preordine):
    totali = totali_ordine(list(preordine.righe.all()))
    preordine.totale = totali['importo']
    preordine.kg = totali['kg']
    preordine.save()


def _riga_json(riga, distanza, giorni, inizio):
    proposta = proposta_unita(riga.media, riga.giacenza, riga.pacchetti_per_unita, giorni, distanza)
    giorni_fine = proposta['giorni_fine']
    if riga.data_fine:
        data_fine = riga.data_fine.isoformat()
    elif giorni_fine is None:
        data_fine = None
    else:
        data_fine = (inizio + timedelta(days=giorni_fine)).isoformat()
    pacchetti = int(riga.unita) * int(riga.pacchetti_per_unita)
    return {
        'aams': riga.aams,
        'descrizione': riga.descrizione,
        'famiglia': riga.famiglia,
        'prezzo': numero_json(riga.prezzo),
        'pacchetti_per_unita': int(riga.pacchetti_per_unita),
        'kg_per_unita': numero_json(riga.kg_per_unita, 3),
        'giacenza': numero_json(riga.giacenza),
        'media': float(riga.media),
        'giorni_fine': giorni_fine,
        'data_fine': data_fine,
        'urgenza': urgenza_data_fine(giorni_fine, distanza, giorni),
        'unita_proposte': riga.unita_proposte,
        'unita': riga.unita,
        'pacchetti': pacchetti,
        'kg': numero_json(int(riga.unita) * _decimal(riga.kg_per_unita), 3),
        'importo': numero_json(riga.importo),
        'corretto_a_mano': riga.corretto_a_mano,
        'giorni_alla_consegna': distanza,
    }


def _preordine_json(preordine, company):
    distanza = _distanza(preordine)
    ultimo = _ultimo(preordine)
    inizio = inizio_vendite(timezone.localdate(), ultimo) if ultimo else timezone.localdate()
    righe = [_riga_json(riga, distanza, preordine.giorni_copertura, inizio) for riga in preordine.righe.all()]
    totali = totali_ordine(righe)
    return {
        'id': preordine.id,
        'stato': preordine.stato,
        'giorni_copertura': preordine.giorni_copertura,
        'data_consegna': preordine.data_consegna.isoformat(),
        'giorni_alla_consegna': distanza,
        'ultimo_giorno_chiuso': ultimo,
        'letto_alle': _letto_alle(preordine),
        'totale': numero_json(preordine.totale),
        'kg': numero_json(preordine.kg, 3),
        'articoli': totali['articoli'],
        'stecche': totali['stecche'],
        'famiglie': list(FAMIGLIE),
        'modificabile': preordine.stato in STATI_MODIFICABILI,
        'agent_online': agent_is_online(company),
        'request_id': preordine.request_id,
        'righe': righe,
        'aggiornato_il': timezone.localtime(preordine.aggiornato_il).isoformat(timespec='seconds'),
    }


def _crea_righe(preordine, dati):
    calcolate, _scartati = calcola_righe(
        dati,
        timezone.localdate(),
        giorni_copertura=preordine.giorni_copertura,
        data_consegna=preordine.data_consegna,
    )
    TabacchiPreordineRiga.objects.bulk_create([
        TabacchiPreordineRiga(
            preordine=preordine,
            aams=riga['aams'],
            descrizione=riga['descrizione'],
            famiglia=riga['famiglia'],
            prezzo=riga['prezzo'],
            pacchetti_per_unita=riga['pacchetti_per_unita'],
            kg_per_unita=riga['kg_per_unita'],
            giacenza=riga['giacenza'],
            media=riga['media'],
            data_fine=parse_date(riga['data_fine']) if riga.get('data_fine') else None,
            unita_proposte=riga['unita_proposte'],
            unita=riga['unita'],
            importo=riga['importo'],
        )
        for riga in calcolate
    ])
    _salva_totali(preordine)


def _csv_content(preordine):
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
    writer.writerow([
        'codice_aams', 'descrizione', 'famiglia', 'stecche_o_confezioni', 'pacchetti', 'kg', 'importo',
    ])
    for riga in preordine.righe.filter(unita__gt=0).order_by('aams'):
        pacchetti = int(riga.unita) * int(riga.pacchetti_per_unita)
        kg = _kg(int(riga.unita) * _decimal(riga.kg_per_unita))
        writer.writerow([
            riga.aams,
            riga.descrizione,
            riga.famiglia,
            int(riga.unita),
            pacchetti,
            f'{kg:.3f}'.replace('.', ','),
            f'{_money(riga.importo):.2f}'.replace('.', ','),
        ])
    return '\ufeff' + buffer.getvalue()


@require_auth
def api_tabacchi_preordini(request):
    company, err = _company(request)
    if err:
        return err
    if request.method == 'GET':
        rows = TabacchiPreordine.objects.filter(company=company).order_by('-creato_il', '-id')[:30]
        return JsonResponse({'status': 'success', 'preordini': [
            {
                'id': row.id,
                'stato': row.stato,
                'data_consegna': row.data_consegna.isoformat(),
                'giorni_copertura': row.giorni_copertura,
                'totale': numero_json(row.totale),
                'kg': numero_json(row.kg, 3),
                'creato_il': timezone.localtime(row.creato_il).isoformat(timespec='seconds'),
            }
            for row in rows
        ], 'agent_online': agent_is_online(company)})
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa GET o POST'}, status=405)
    expire_requests()
    existing = TabaUnoRequest.objects.filter(
        company=company,
        tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
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
        tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
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
def api_tabacchi_preordine_da_richiesta(request, request_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    company, err = _company(request)
    if err:
        return err
    data = _body(request)
    if data is None:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    lettura = TabaUnoRequest.objects.filter(
        id=request_id, company=company, tipo=TabaUnoRequest.TIPO_PREORDINE_TABACCHI,
    ).first()
    if not lettura:
        return JsonResponse({'status': 'error', 'error': 'Richiesta non trovata.'}, status=404)
    if lettura.status != TabaUnoRequest.DONE or not isinstance(lettura.payload, dict):
        return JsonResponse({'status': 'error', 'error': 'La lettura TabaUno non è pronta.'}, status=409)
    giorni = _giorni(data.get('giorni_copertura'), 7)
    if giorni is None:
        return JsonResponse({'status': 'error', 'error': 'Giorni di copertura non validi.'}, status=400)
    default_consegna = prossimo_giorno_consegna(
        timezone.localdate(), _giorno_consegna_setting(company),
    )
    consegna = _consegna(data.get('data_consegna'), default_consegna)
    if not consegna:
        return JsonResponse({'status': 'error', 'error': 'Data di consegna non valida.'}, status=400)
    esistente = TabacchiPreordine.objects.filter(company=company, request=lettura).order_by('-id').first()
    if esistente:
        return JsonResponse({'status': 'success', 'created': False, 'preordine': _preordine_json(esistente, company)})
    preordine = TabacchiPreordine.objects.create(
        company=company,
        creato_da=request.user,
        request=lettura,
        data_consegna=consegna,
        giorni_copertura=giorni,
    )
    _crea_righe(preordine, lettura.payload)
    preordine.refresh_from_db()
    return JsonResponse({'status': 'success', 'created': True, 'preordine': _preordine_json(preordine, company)}, status=201)


@require_auth
def api_tabacchi_preordine_detail(request, preordine_id):
    company, err = _company(request)
    if err:
        return err
    preordine = TabacchiPreordine.objects.filter(id=preordine_id, company=company).first()
    if not preordine:
        return JsonResponse({'status': 'error', 'error': 'Preordine non trovato.'}, status=404)
    if request.method == 'GET':
        return JsonResponse({'status': 'success', 'preordine': _preordine_json(preordine, company)})
    if request.method == 'DELETE':
        preordine.delete()
        return JsonResponse({'status': 'success'})
    if request.method != 'PATCH':
        return JsonResponse({'status': 'error', 'error': 'Usa GET, PATCH o DELETE'}, status=405)
    if preordine.stato not in STATI_MODIFICABILI:
        return JsonResponse({'status': 'error', 'error': 'Ordine non modificabile.'}, status=409)
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
    if preordine.stato == TabacchiPreordine.ANNULLATO:
        preordine.stato = TabacchiPreordine.BOZZA
    preordine.save()
    ultimo = _ultimo(preordine)
    if not ultimo:
        return JsonResponse({'status': 'error', 'error': 'Manca la data di chiusura letta da TabaUno.'}, status=409)
    distanza = giorni_alla_consegna(timezone.localdate(), ultimo, preordine.data_consegna)
    inizio = inizio_vendite(timezone.localdate(), ultimo)
    inviate = {}
    for item in data.get('righe') or []:
        if isinstance(item, dict) and item.get('aams') is not None:
            try:
                inviate[str(item['aams'])] = int(item.get('unita') or 0)
            except (TypeError, ValueError):
                return JsonResponse({'status': 'error', 'error': 'Quantità non valide.'}, status=400)
    for riga in preordine.righe.all():
        proposta = _applica_proposta(
            riga,
            preordine.giorni_copertura,
            distanza,
            inviate.get(riga.aams),
            riga.aams in inviate,
        )
        if proposta['giorni_fine'] is None:
            riga.data_fine = None
        else:
            riga.data_fine = inizio + timedelta(days=proposta['giorni_fine'])
        riga.save()
    _salva_totali(preordine)
    preordine.refresh_from_db()
    return JsonResponse({'status': 'success', 'preordine': _preordine_json(preordine, company)})


@require_auth
def api_tabacchi_preordine_csv(request, preordine_id):
    if request.method != 'GET':
        return JsonResponse({'status': 'error', 'error': 'Usa GET'}, status=405)
    company, err = _company(request)
    if err:
        return err
    preordine = TabacchiPreordine.objects.filter(id=preordine_id, company=company).first()
    if not preordine:
        return JsonResponse({'status': 'error', 'error': 'Preordine non trovato.'}, status=404)
    content = _csv_content(preordine)
    response = HttpResponse(content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="ordine-tabacchi-{preordine.id}.csv"'
    if preordine.stato == TabacchiPreordine.BOZZA:
        preordine.stato = TabacchiPreordine.ESPORTATO
        preordine.save(update_fields=['stato', 'aggiornato_il'])
    return response
