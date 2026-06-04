import json
from decimal import Decimal, InvalidOperation

from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.db.models import Max
from django.http import HttpResponse, JsonResponse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods

from .company_scope import bind_company
from .models import AppSetting, Cliente, Ricevuta, RicevutaRiga, ValoreBollato
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
        'numero_progressivo': int(row.numero_progressivo or row.id),
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


def _get_ricevute_counter(company):
    raw = (
        AppSetting.objects.filter(company=company, key='ricevute_progressive_counter')
        .values_list('value', flat=True)
        .first()
    )
    try:
        value = int(str(raw).strip()) if raw is not None else 0
    except (TypeError, ValueError):
        value = 0
    return max(0, value)


def _max_numero_progressivo(company):
    agg = Ricevuta.objects.filter(company=company).aggregate(m=Max('numero_progressivo'))['m']
    return int(agg or 0)


def _prossimo_numero_progressivo(company):
    return max(_get_ricevute_counter(company), _max_numero_progressivo(company)) + 1


def _sync_ricevute_counter(company):
    """Allinea il contatore al massimo progressivo già emesso."""
    effective = max(_get_ricevute_counter(company), _max_numero_progressivo(company))
    AppSetting.objects.update_or_create(
        company=company,
        key='ricevute_progressive_counter',
        defaults={'value': str(effective)},
    )
    return effective


def _parse_numero_progressivo(value, company, *, exclude_id=None):
    try:
        numero = int(value)
    except (TypeError, ValueError):
        raise ValueError('Numero progressivo non valido.')
    if numero < 1:
        raise ValueError('Il numero progressivo deve essere almeno 1.')

    qs = Ricevuta.objects.filter(company=company, numero_progressivo=numero)
    if exclude_id is not None:
        qs = qs.exclude(id=exclude_id)
    if qs.exists():
        raise ValueError(f'Il numero progressivo {numero} è già assegnato a un\'altra ricevuta.')
    return numero


def _get_mail_setting(company, key, default=''):
    raw = (
        AppSetting.objects.filter(company=company, key=key)
        .values_list('value', flat=True)
        .first()
    )
    if raw is None:
        return default
    return str(raw).strip()


def _get_mail_settings(company):
    host = _get_mail_setting(company, 'smtp_host')
    port_raw = _get_mail_setting(company, 'smtp_port', '587')
    username = _get_mail_setting(company, 'smtp_username')
    password = _get_mail_setting(company, 'smtp_password')
    from_email = _get_mail_setting(company, 'smtp_from_email')
    use_tls = _get_mail_setting(company, 'smtp_use_tls', '1').lower() in {'1', 'true', 'yes', 'on'}
    use_ssl = _get_mail_setting(company, 'smtp_use_ssl', '0').lower() in {'1', 'true', 'yes', 'on'}
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        port = 587
    return {
        'host': host,
        'port': port,
        'username': username,
        'password': password,
        'from_email': from_email,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
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
            'prossimo_progressivo': _prossimo_numero_progressivo(company),
        })

    try:
        data = json.loads(request.body or '{}')
        fields = _parse_ricevuta_body(data, company)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    try:
        if 'numero_progressivo' in data and data.get('numero_progressivo') not in (None, ''):
            next_number = _parse_numero_progressivo(data.get('numero_progressivo'), company)
        else:
            next_number = _prossimo_numero_progressivo(company)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

    with transaction.atomic():
        ricevuta = Ricevuta.objects.create(
            company=company,
            cliente=fields['cliente'],
            date=fields['date'],
            operator=request.user.username,
            note=fields['note'],
            numero_progressivo=next_number,
        )
        for riga in fields['righe']:
            RicevutaRiga.objects.create(ricevuta=ricevuta, **riga)
        _sync_ricevute_counter(company)

    ricevuta = Ricevuta.objects.select_related('cliente').prefetch_related('righe').get(pk=ricevuta.pk)
    return JsonResponse({'status': 'success', 'data': _serialize_ricevuta(ricevuta, detail=True)}, status=201)


@require_auth
@require_http_methods(['GET', 'PUT', 'DELETE'])
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
        _sync_ricevute_counter(company)
        return JsonResponse({'status': 'success'})

    if request.method == 'PUT':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)

        if 'numero_progressivo' not in data:
            return JsonResponse({'status': 'error', 'error': 'numero_progressivo obbligatorio'}, status=400)
        try:
            row.numero_progressivo = _parse_numero_progressivo(
                data.get('numero_progressivo'),
                company,
                exclude_id=row.id,
            )
        except ValueError as exc:
            return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)

        row.save(update_fields=['numero_progressivo'])
        _sync_ricevute_counter(company)
        row = (
            Ricevuta.objects.filter(company=company)
            .select_related('cliente')
            .prefetch_related('righe')
            .get(id=ricevuta_id)
        )
        return JsonResponse({
            'status': 'success',
            'data': _serialize_ricevuta(row, detail=True),
            'prossimo_progressivo': _prossimo_numero_progressivo(company),
        })

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
    response['Content-Disposition'] = f'inline; filename="ricevuta-{row.numero_progressivo}.pdf"'
    return response


@require_auth
@require_http_methods(['POST'])
def api_ricevuta_send_email(request, ricevuta_id):
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

    recipient = (row.cliente.email or '').strip()
    if not recipient:
        return JsonResponse({'status': 'error', 'error': 'Il cliente non ha una email registrata.'}, status=400)

    smtp = _get_mail_settings(company)
    if not smtp['host'] or not smtp['username'] or not smtp['password'] or not smtp['from_email']:
        return JsonResponse(
            {'status': 'error', 'error': 'Configura SMTP in Impostazioni prima di inviare email.'},
            status=400,
        )

    try:
        pdf_bytes = render_ricevuta_pdf(row)
    except RuntimeError as exc:
        return JsonResponse({'status': 'error', 'error': str(exc)}, status=503)

    subject = f'Ricevuta n. {row.numero_progressivo} - {company.denominazione}'
    body = (
        f"Buongiorno {row.cliente.ragione_sociale},\n\n"
        f"in allegato trova la ricevuta n. {row.numero_progressivo} del {row.date.strftime('%d/%m/%Y')}.\n\n"
        "Cordiali saluti."
    )
    filename = f'ricevuta-{row.numero_progressivo}.pdf'

    try:
        connection = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=smtp['host'],
            port=smtp['port'],
            username=smtp['username'],
            password=smtp['password'],
            use_tls=smtp['use_tls'],
            use_ssl=smtp['use_ssl'],
        )
        message = EmailMessage(
            subject=subject,
            body=body,
            from_email=smtp['from_email'],
            to=[recipient],
            connection=connection,
        )
        message.attach(filename, pdf_bytes, 'application/pdf')
        message.send(fail_silently=False)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'error': f'Invio email fallito: {exc}'}, status=502)

    return JsonResponse({
        'status': 'success',
        'message': f'Email inviata con successo a {recipient}.',
        'data': {
            'email': recipient,
            'numero_progressivo': int(row.numero_progressivo),
        },
    })
