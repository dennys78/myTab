import json

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from .company_scope import bind_company
from .models import Cliente, ValoreBollato
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
