import json
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .company_scope import bind_company
from .models import Cliente, Ricevuta, RicevutaRiga, ValoreBollato
from .ricevuta_pdf import render_ricevuta_pdf
from .views import require_auth


def _serialize_cliente(row):
    return {
        'id': row.id,
        'ragione_sociale': row.ragione_sociale,
        'indirizzo': row.indirizzo,
        'cf_piva': row.cf_piva,
        'email': row.email,
    }


def _serialize_valore_bollato(row):
    return {
        'id': row.id,
        'descrizione': row.descrizione,
        'importo': float(row.importo),
    }


def _parse_cliente_body(data):
    ragione_sociale = str(data.get('ragione_sociale', '')).strip()
    if not ragione_sociale:
        raise ValueError('La ragione sociale è obbligatoria.')
    return {
        'ragione_sociale': ragione_sociale,
        'indirizzo': str(data.get('indirizzo', '')).strip(),
        'cf_piva': str(data.get('cf_piva', '')).strip(),
        'email': str(data.get('email', '')).strip(),
    }


def _parse_valore_bollato_body(data):
    descrizione = str(data.get('descrizione', '')).strip()
    if not descrizione:
        raise ValueError('La descrizione è obbligatoria.')
    try:
        importo = float(data.get('importo', 0))
    except (TypeError, ValueError):
        raise ValueError('Importo non valido.')
    if importo < 0:
        raise ValueError('Importo non valido.')
    return {'descrizione': descrizione, 'importo': importo}


@require_auth
@require_http_methods(['GET', 'POST'])
def api_clienti(request):
    company, err = bind_company(request)
    if err:
        return err

    if request.method == 'GET':
        rows = Cliente.objects.filter(company=company)
        return JsonResponse({
            'status': 'success',
            'data': [_serialize_cliente(c) for c in rows],
        })

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_cliente_body(data)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    row = Cliente.objects.create(company=company, **fields)
    return JsonResponse({'status': 'success', 'data': _serialize_cliente(row)}, status=201)


@require_auth
@require_http_methods(['PUT', 'DELETE'])
def api_cliente_detail(request, cliente_id):
    company, err = bind_company(request)
    if err:
        return err

    try:
        row = Cliente.objects.get(id=cliente_id, company=company)
    except Cliente.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Cliente non trovato'}, status=404)

    if request.method == 'DELETE':
        row.delete()
        return JsonResponse({'status': 'success'})

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_cliente_body(data)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    for key, value in fields.items():
        setattr(row, key, value)
    row.save()
    return JsonResponse({'status': 'success', 'data': _serialize_cliente(row)})


@require_auth
@require_http_methods(['GET', 'POST'])
def api_valori_bollati(request):
    company, err = bind_company(request)
    if err:
        return err

    if request.method == 'GET':
        rows = ValoreBollato.objects.filter(company=company)
        return JsonResponse({
            'status': 'success',
            'data': [_serialize_valore_bollato(v) for v in rows],
        })

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_valore_bollato_body(data)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    row = ValoreBollato.objects.create(company=company, **fields)
    return JsonResponse({'status': 'success', 'data': _serialize_valore_bollato(row)}, status=201)


@require_auth
@require_http_methods(['PUT', 'DELETE'])
def api_valore_bollato_detail(request, valore_id):
    company, err = bind_company(request)
    if err:
        return err

    try:
        row = ValoreBollato.objects.get(id=valore_id, company=company)
    except ValoreBollato.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Valore bollato non trovato'}, status=404)

    if request.method == 'DELETE':
        row.delete()
        return JsonResponse({'status': 'success'})

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_valore_bollato_body(data)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    row.descrizione = fields['descrizione']
    row.importo = fields['importo']
    row.save()
    return JsonResponse({'status': 'success', 'data': _serialize_valore_bollato(row)})


def _money_decimal(value, field_name='Importo'):
    try:
        amount = Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{field_name} non valido.')
    if amount < 0:
        raise ValueError(f'{field_name} non valido.')
    return amount.quantize(Decimal('0.01'))


def _serialize_riga(row):
    qty = int(row.quantita or 1)
    unit = float(row.importo_unitario)
    return {
        'id': row.id,
        'tipo': row.tipo,
        'tipo_label': row.get_tipo_display(),
        'descrizione': row.descrizione,
        'importo_unitario': unit,
        'quantita': qty,
        'importo_totale': float(row.importo_unitario * qty),
        'valore_bollato_id': row.valore_bollato_id,
    }


def _serialize_ricevuta(row, *, detail=False):
    righe = list(row.righe.all())
    totale = sum((r.importo_unitario * int(r.quantita or 1) for r in righe), Decimal('0'))
    payload = {
        'id': row.id,
        'date': row.date.isoformat(),
        'cliente_id': row.cliente_id,
        'cliente': _serialize_cliente(row.cliente),
        'operator': row.operator,
        'note': row.note,
        'totale': float(totale.quantize(Decimal('0.01'))),
        'created_at': row.created_at.isoformat(),
    }
    if detail:
        payload['righe'] = [_serialize_riga(r) for r in righe]
    return payload


def _parse_riga_body(data, company):
    tipo = str(data.get('tipo', '')).strip()
    if tipo not in {RicevutaRiga.TIPO_VALORE_BOLLATO, RicevutaRiga.TIPO_CONTRIBUTO_UNIFICATO}:
        raise ValueError('Tipo articolo non valido.')

    try:
        quantita = int(data.get('quantita', 1) or 1)
    except (TypeError, ValueError):
        raise ValueError('Quantità non valida.')
    if quantita < 1:
        raise ValueError('La quantità deve essere almeno 1.')

    valore_bollato = None
    if tipo == RicevutaRiga.TIPO_VALORE_BOLLATO:
        vb_id = data.get('valore_bollato_id')
        if vb_id:
            valore_bollato = ValoreBollato.objects.get(id=vb_id, company=company)
            descrizione = valore_bollato.descrizione
            importo_unitario = valore_bollato.importo
        else:
            importo_unitario = _money_decimal(
                data.get('importo_unitario', data.get('valore', 0)),
                'Valore',
            )
            if importo_unitario <= 0:
                raise ValueError('Valore obbligatorio.')
            descrizione = f'Valore bollato € {importo_unitario:.2f}'.replace('.', ',')
    else:
        descrizione = 'Contributo unificato'
        importo_unitario = _money_decimal(data.get('importo_unitario', 0), 'Importo contributo')

    return {
        'tipo': tipo,
        'descrizione': descrizione,
        'importo_unitario': importo_unitario,
        'quantita': quantita,
        'valore_bollato': valore_bollato,
    }


def _parse_ricevuta_body(data, company):
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        raise ValueError('Seleziona un cliente.')
    try:
        cliente = Cliente.objects.get(id=cliente_id, company=company)
    except Cliente.DoesNotExist:
        raise ValueError('Cliente non trovato.')

    date_str = str(data.get('date', '')).strip()
    parsed_date = parse_date(date_str)
    if not parsed_date:
        raise ValueError('Data ricevuta non valida.')

    righe_data = data.get('righe') or []
    if not righe_data:
        raise ValueError('Aggiungi almeno un articolo alla ricevuta.')

    righe = [_parse_riga_body(item, company) for item in righe_data]
    return {
        'cliente': cliente,
        'date': parsed_date,
        'note': str(data.get('note', '')).strip(),
        'righe': righe,
    }


@require_auth
@require_http_methods(['GET', 'POST'])
def api_ricevute_emesse(request):
    company, err = bind_company(request)
    if err:
        return err

    if request.method == 'GET':
        rows = (
            Ricevuta.objects.filter(company=company)
            .select_related('cliente')
            .prefetch_related('righe')
        )
        return JsonResponse({
            'status': 'success',
            'data': [_serialize_ricevuta(r) for r in rows],
        })

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_ricevuta_body(data, company)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    with transaction.atomic():
        ricevuta = Ricevuta.objects.create(
            company=company,
            cliente=fields['cliente'],
            date=fields['date'],
            operator=request.user.username,
            note=fields['note'],
        )
        for riga in fields['righe']:
            RicevutaRiga.objects.create(ricevuta=ricevuta, **riga)

    ricevuta = Ricevuta.objects.select_related('cliente').prefetch_related('righe').get(pk=ricevuta.pk)
    return JsonResponse({'status': 'success', 'data': _serialize_ricevuta(ricevuta, detail=True)}, status=201)


@require_auth
@require_http_methods(['GET', 'DELETE'])
def api_ricevuta_emessa_detail(request, ricevuta_id):
    company, err = bind_company(request)
    if err:
        return err

    try:
        row = (
            Ricevuta.objects.filter(company=company)
            .select_related('cliente')
            .prefetch_related('righe')
            .get(id=ricevuta_id)
        )
    except Ricevuta.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Ricevuta non trovata'}, status=404)

    if request.method == 'DELETE':
        row.delete()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'success', 'data': _serialize_ricevuta(row, detail=True)})


@require_auth
@require_http_methods(['GET'])
def api_ricevuta_pdf(request, ricevuta_id):
    company, err = bind_company(request)
    if err:
        return err

    try:
        row = (
            Ricevuta.objects.filter(company=company)
            .select_related('cliente', 'company')
            .prefetch_related('righe')
            .get(id=ricevuta_id)
        )
    except Ricevuta.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Ricevuta non trovata'}, status=404)

    try:
        pdf_bytes = render_ricevuta_pdf(row)
    except RuntimeError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=503)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="ricevuta-{row.id}.pdf"'
    return response
