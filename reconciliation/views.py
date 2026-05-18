from __future__ import annotations

import json
import base64
import os
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.models import User
from difflib import get_close_matches
from .models import (
    AcquisitionDraft,
    CashClosure,
    CashClosureItem,
    Department,
    AppSetting,
    Versamento,
    FondoCassaMovimento,
)
from .ocr_parser import parse_closure_receipt
import pytesseract
from PIL import Image, ImageEnhance


MONEY_ZERO = Decimal('0.00')


def _money(value, default=MONEY_ZERO):
    if value in (None, ''):
        return default
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f'Importo non valido: {value}')


def _money_number(value):
    return float(_money(value))


# ── AUTH HELPERS ─────────────────────────────────────────────────────────────

def _is_admin(user):
    return user.is_staff or user.is_superuser

def _user_info(user):
    return {
        'id': user.id,
        'username': user.username,
        'role': 'amministratore' if _is_admin(user) else 'utente',
    }

def require_auth(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper

def require_admin(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
        if not _is_admin(request.user):
            return JsonResponse({'status': 'error', 'error': 'Accesso negato'}, status=403)
        return view_func(request, *args, **kwargs)
    return wrapper


# ── AUTH VIEWS ───────────────────────────────────────────────────────────────

def api_login(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'error': 'Usa POST'}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        user = authenticate(request, username=username, password=password)
        if user is None:
            return JsonResponse({'status': 'error', 'error': 'Username o password errati'}, status=401)
        auth_login(request, user)
        return JsonResponse({'status': 'success', 'data': _user_info(user)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

def api_logout(request):
    auth_logout(request)
    return JsonResponse({'status': 'success'})

@ensure_csrf_cookie
def api_me(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    return JsonResponse({'status': 'success', 'data': _user_info(request.user)})


# ── GESTIONE UTENTI (solo amministratori) ────────────────────────────────────

@require_admin
def api_users_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    users = User.objects.all().order_by('username')
    return JsonResponse({'status': 'success', 'data': [_user_info(u) for u in users]})

@require_admin
def api_user_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'utente')
        if not username or not password:
            return JsonResponse({'status': 'error', 'error': 'Username e password obbligatori'})
        if User.objects.filter(username=username).exists():
            return JsonResponse({'status': 'error', 'error': 'Username già in uso'})
        user = User(username=username, is_staff=(role == 'amministratore'))
        user.set_password(password)
        user.save()
        return JsonResponse({'status': 'success', 'data': _user_info(user)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

@require_admin
def api_user_delete(request, user_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error'}, status=405)
    if user_id == request.user.id:
        return JsonResponse({'status': 'error', 'error': 'Non puoi eliminare te stesso'})
    try:
        User.objects.get(id=user_id).delete()
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Utente non trovato'}, status=404)

@require_admin
def api_user_change_password(request, user_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        password = data.get('password', '').strip()
        if not password:
            return JsonResponse({'status': 'error', 'error': 'Password obbligatoria'})
        user = User.objects.get(id=user_id)
        user.set_password(password)
        user.save()
        return JsonResponse({'status': 'success'})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Utente non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_user_update(request, user_id):
    if request.method not in ['POST', 'PUT']:
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        user = User.objects.get(id=user_id)

        username = data.get('username', user.username).strip()
        password = data.get('password', '').strip()
        role = data.get('role', 'amministratore' if user.is_staff else 'utente')

        if not username:
            return JsonResponse({'status': 'error', 'error': 'Username obbligatorio'})
        if User.objects.exclude(id=user.id).filter(username=username).exists():
            return JsonResponse({'status': 'error', 'error': 'Username già in uso'})

        user.username = username
        user.is_staff = role == 'amministratore'
        if password:
            user.set_password(password)
        user.save()
        if user.id == request.user.id and password:
            update_session_auth_hash(request, user)
        return JsonResponse({'status': 'success', 'data': _user_info(user)})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Utente non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


def _preprocess(img):
    img = img.convert('L')
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


def _resolve_dept(name: str, known: list) -> str | None:
    """Canonical department name for `name` from the known list.

    Priority:
    1. Exact match
    2. A known dept is a prefix of `name` (≥5 chars) — handles
       'LOTTOMATICA(LOTTO + 10&LOTTO)' → 'LOTTOMATICA'
    3. Fuzzy match with cutoff 0.6
    """
    if not known or not name:
        return None
    if name in known:
        return name
    for k in known:
        if len(k) >= 5 and name.startswith(k):
            return k
    matches = get_close_matches(name, known, n=1, cutoff=0.6)
    return matches[0] if matches else None


@require_auth
def api_insert_closure(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            date_str = data.get('date')
            operator = request.user.username
            summary = data.get('summary', {})
            items = data.get('items', [])
            
            if not date_str:
                return JsonResponse({'error': 'Campo "date" obbligatorio (Formato YYYY-MM-DD)'}, status=400)
                
            parsed_date = parse_date(date_str)
            if not parsed_date:
                return JsonResponse({'error': 'Formato data non valido, usa YYYY-MM-DD'}, status=400)

            with transaction.atomic():
                draft = None
                draft_id = data.get('draft_id')
                if draft_id:
                    draft = AcquisitionDraft.objects.filter(id=draft_id, status='pending').first()

                # Inserimento Master
                closure = CashClosure.objects.create(
                    date=parsed_date,
                    operator=operator,
                    submitted_by=draft.operator if draft else '',
                    contanti=_money(summary.get('contanti')),
                    pag_pos=_money(summary.get('pag_pos')),
                    cassa_auto=_money(summary.get('cassa_auto')),
                    reso_cont=_money(summary.get('reso_cont')),
                    reso_auto=_money(summary.get('reso_auto')),
                    distrib=_money(summary.get('distrib')),
                    totale_generale=_money(summary.get('totale')),
                    totale_cassetto=_money(summary.get('totale_cassetto')),
                    differenza=_money(summary.get('differenza')),
                )

                # Auto-popola archivio reparti e inserisce le righe
                known_depts = list(Department.objects.values_list('name', flat=True))
                for item in items:
                    dept_name = item.get('descrizione', '').strip()
                    if dept_name and dept_name != 'Reparto Sconosciuto':
                        resolved = _resolve_dept(dept_name, known_depts)
                        if resolved:
                            dept_name = resolved
                        else:
                            Department.objects.get_or_create(name=dept_name)
                            known_depts.append(dept_name)

                    CashClosureItem.objects.create(
                        closure=closure,
                        department_name=dept_name or 'Reparto Sconosciuto',
                        incomes=_money(item.get('entrate')),
                        expenses=_money(item.get('uscite')),
                        balance=_money(item.get('saldo'))
                    )

                if draft:
                    AcquisitionDraft.objects.filter(id=draft.id, status='pending').update(
                        status='completed',
                        completed_at=timezone.now(),
                    )
            
            return JsonResponse({
                'status': 'success', 
                'message': f'Chiusura cassa inserita correttamente con {len(items)} voci.',
                'id': closure.id
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON non valido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

@require_admin
def api_extract_closure(request):
    if request.method == 'POST':
        if not request.FILES:
            return JsonResponse({'error': 'Nessuna immagine fornita.'}, status=400)
            
        try:
            full_text = ""
            for file_key in request.FILES:
                img = Image.open(request.FILES[file_key])
                img = _preprocess(img)
                full_text += pytesseract.image_to_string(img, lang='ita', config='--psm 6') + "\n"

            parsed_data = parse_closure_receipt(full_text)
            date_str = parsed_data['date'].isoformat() if parsed_data['date'] else ""

            # Risolve nomi reparti contro archivio (exact → prefix → fuzzy)
            known = list(Department.objects.values_list('name', flat=True))
            for item in parsed_data['items']:
                resolved = _resolve_dept(item['descrizione'], known)
                if resolved:
                    item['descrizione'] = resolved

            # Dedup post-resolve: nomi diversi convergono sullo stesso canonico
            seen: dict = {}
            for item in parsed_data['items']:
                name = item['descrizione']
                if name not in seen:
                    seen[name] = item
                elif seen[name]['entrate'] == 0 and seen[name]['uscite'] == 0:
                    seen[name] = item
            parsed_data['items'] = list(seen.values())

            response_data = {
                'date': date_str,
                'operator': 'Sistema Esterno',
                'summary': {
                    'contanti':   parsed_data['contanti'],
                    'pag_pos':    parsed_data['pag_pos'],
                    'cassa_auto': parsed_data['cassa_auto'],
                    'reso_cont':  parsed_data['reso_cont'],
                    'reso_auto':  parsed_data['reso_auto'],
                    'distrib':    parsed_data['distrib'],
                    'totale':     parsed_data['total_in'],
                },
                'items': parsed_data['items'],
                'raw_text': full_text,
            }

            return JsonResponse({'status': 'success', 'data': response_data})

        except Exception as e:
            return JsonResponse({'error': f"Errore elaborazione immagine: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

@require_admin
def api_list_closures(request):
    if request.method == 'GET':
        closures = CashClosure.objects.all().prefetch_related('items')
        data = []
        for c in closures:
            items = []
            for item in c.items.all():
                items.append({
                    'id': item.id,
                    'descrizione': item.department_name,
                    'entrate': float(item.incomes),
                    'uscite': float(item.expenses),
                    'saldo': float(item.balance)
                })
            
            data.append({
                'id': c.id,
                'date': c.date.isoformat(),
                'operator': c.operator,
                'submitted_by': c.submitted_by,
                'summary': {
                    'contanti': float(c.contanti),
                    'pag_pos': float(c.pag_pos),
                    'cassa_auto': float(c.cassa_auto),
                    'reso_cont': float(c.reso_cont),
                    'reso_auto': float(c.reso_auto),
                    'distrib': float(c.distrib),
                    'totale': float(c.totale_generale),
                    'totale_cassetto': float(c.totale_cassetto),
                    'differenza': float(c.differenza),
                },
                'items': items
            })
            
        return JsonResponse({'status': 'success', 'data': data})
        
    return JsonResponse({'error': 'Metodo non consentito. Usa GET.'}, status=405)
@require_admin
def api_update_closure(request, closure_id):
    if request.method in ['POST', 'PUT']:
        try:
            closure = CashClosure.objects.get(id=closure_id)
            data = json.loads(request.body)
            
            # Aggiorna solo se presenti nel payload
            if 'contanti' in data: closure.contanti = _money(data['contanti'])
            if 'pag_pos' in data: closure.pag_pos = _money(data['pag_pos'])
            if 'cassa_auto' in data: closure.cassa_auto = _money(data['cassa_auto'])
            if 'reso_cont' in data: closure.reso_cont = _money(data['reso_cont'])
            if 'reso_auto' in data: closure.reso_auto = _money(data['reso_auto'])
            if 'distrib' in data: closure.distrib = _money(data['distrib'])
            if 'totale' in data: closure.totale_generale = _money(data['totale'])
            if 'totale_cassetto' in data: closure.totale_cassetto = _money(data['totale_cassetto'])
            if 'differenza' in data: closure.differenza = _money(data['differenza'])
            
            closure.save()

            deleted_item_ids = data.get('deleted_item_ids', [])
            if deleted_item_ids:
                CashClosureItem.objects.filter(id__in=deleted_item_ids, closure=closure).delete()
            
            # Aggiorna gli items se presenti
            items_data = data.get('items', [])
            for item_data in items_data:
                item_id = item_data.get('id')
                if item_id:
                    try:
                        item = CashClosureItem.objects.get(id=item_id, closure=closure)
                        if 'entrate' in item_data: item.incomes = _money(item_data['entrate'])
                        if 'uscite' in item_data: item.expenses = _money(item_data['uscite'])
                        if 'saldo' in item_data: item.balance = _money(item_data['saldo'])
                        if 'descrizione' in item_data: item.department_name = str(item_data['descrizione'])
                        item.save()
                    except CashClosureItem.DoesNotExist:
                        pass # Ignora gli ID non validi
                        
            return JsonResponse({'status': 'success', 'message': 'Chiusura aggiornata correttamente.'})
            
        except CashClosure.DoesNotExist:
            return JsonResponse({'error': 'Chiusura non trovata'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON non valido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Metodo non consentito. Usa PUT o POST.'}, status=405)

@require_admin
def api_delete_closure(request, closure_id):
    if request.method == 'DELETE':
        try:
            closure = CashClosure.objects.get(id=closure_id)
            closure.delete()
            return JsonResponse({'status': 'success', 'message': 'Chiusura eliminata correttamente.'})
        except CashClosure.DoesNotExist:
            return JsonResponse({'error': 'Chiusura non trovata'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Metodo non consentito. Usa DELETE.'}, status=405)


# ── REPARTI ──────────────────────────────────────────────────────────────────

@require_admin
def api_list_departments(request):
    if request.method == 'GET':
        data = [{'id': d.id, 'name': d.name} for d in Department.objects.all()]
        return JsonResponse({'status': 'success', 'data': data})
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_create_department(request):
    if request.method == 'POST':
        try:
            name = json.loads(request.body).get('name', '').strip().upper()
            if not name:
                return JsonResponse({'error': 'Nome obbligatorio.'}, status=400)
            dept, created = Department.objects.get_or_create(name=name)
            return JsonResponse({'status': 'success', 'id': dept.id, 'name': dept.name},
                                status=201 if created else 200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_update_department(request, dept_id):
    if request.method in ['POST', 'PUT']:
        try:
            dept = Department.objects.get(id=dept_id)
            name = json.loads(request.body).get('name', '').strip().upper()
            if not name:
                return JsonResponse({'error': 'Nome obbligatorio.'}, status=400)
            dept.name = name
            dept.save()
            return JsonResponse({'status': 'success', 'id': dept.id, 'name': dept.name})
        except Department.DoesNotExist:
            return JsonResponse({'error': 'Reparto non trovato.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_delete_department(request, dept_id):
    if request.method == 'DELETE':
        try:
            Department.objects.get(id=dept_id).delete()
            return JsonResponse({'status': 'success'})
        except Department.DoesNotExist:
            return JsonResponse({'error': 'Reparto non trovato.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


# ── IMPOSTAZIONI ─────────────────────────────────────────────────────────────

def _get_groq_key():
    try:
        key = AppSetting.objects.get(key='groq_api_key').value.strip()
        if key:
            return key
    except AppSetting.DoesNotExist:
        pass
    return os.environ.get('GROQ_API_KEY', '').strip()


def _get_gemini_key():
    try:
        key = AppSetting.objects.get(key='gemini_api_key').value.strip()
        if key:
            return key
    except AppSetting.DoesNotExist:
        pass
    return os.environ.get('GEMINI_API_KEY', '').strip()


def _get_ai_provider():
    try:
        provider = AppSetting.objects.get(key='ai_acquisition_provider').value.strip().lower()
    except AppSetting.DoesNotExist:
        provider = ''
    return provider if provider in {'groq', 'gemini'} else 'groq'


def _set_ai_provider(provider):
    provider = str(provider or '').strip().lower()
    if provider not in {'groq', 'gemini'}:
        raise ValueError('Provider IA non valido.')
    AppSetting.objects.update_or_create(
        key='ai_acquisition_provider',
        defaults={'value': provider},
    )


def _get_telegram_token():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        try:
            token = AppSetting.objects.get(key='telegram_bot_token').value.strip()
        except AppSetting.DoesNotExist:
            pass
    return token


def _get_setting_money(key):
    try:
        return _money(AppSetting.objects.get(key=key).value)
    except AppSetting.DoesNotExist:
        return MONEY_ZERO


def _set_setting_money(key, value):
    AppSetting.objects.update_or_create(
        key=key,
        defaults={'value': str(_money(value))},
    )


def _get_telegram_chat_ids():
    chat_ids = set(
        AcquisitionDraft.objects
        .exclude(telegram_chat_id='')
        .values_list('telegram_chat_id', flat=True)
    )
    try:
        raw = AppSetting.objects.get(key='telegram_chat_ids').value
        chat_ids.update(str(chat_id) for chat_id in json.loads(raw))
    except (AppSetting.DoesNotExist, json.JSONDecodeError, TypeError):
        pass
    return sorted(str(chat_id) for chat_id in chat_ids if str(chat_id).strip())


def _send_telegram_message(token, chat_id, text):
    data = urllib.parse.urlencode({
        'chat_id': chat_id,
        'text': text,
    }).encode('utf-8')
    req = urllib.request.Request(
        f'https://api.telegram.org/bot{token}/sendMessage',
        data=data,
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=8) as response:
        return response.status == 200


@require_admin
def api_get_settings(request):
    if request.method == 'GET':
        return JsonResponse({
            'status': 'success',
            'data': {
                'groq_key_configured': bool(_get_groq_key()),
                'gemini_key_configured': bool(_get_gemini_key()),
                'ai_acquisition_provider': _get_ai_provider(),
                'telegram_token_configured': bool(_get_telegram_token()),
                'saldo_cassa': float(_get_saldo_cassa()),
                'fondo_cassa': float(_get_fondo_cassa()),
            },
        })
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_save_settings(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            key = data.get('groq_api_key', '').strip()
            if key:
                AppSetting.objects.update_or_create(
                    key='groq_api_key',
                    defaults={'value': key},
                )

            gemini_key = data.get('gemini_api_key', '').strip()
            if gemini_key:
                AppSetting.objects.update_or_create(
                    key='gemini_api_key',
                    defaults={'value': gemini_key},
                )

            if 'ai_acquisition_provider' in data:
                _set_ai_provider(data.get('ai_acquisition_provider'))

            telegram_token = data.get('telegram_bot_token', '').strip()
            if telegram_token:
                AppSetting.objects.update_or_create(
                    key='telegram_bot_token',
                    defaults={'value': telegram_token},
                )

            if 'saldo_cassa' in data:
                target_saldo = _money(data['saldo_cassa'])
                _set_setting_money('saldo_cassa_adjustment', target_saldo - _get_saldo_cassa_base())

            if 'fondo_cassa' in data:
                target_fondo = _money(data['fondo_cassa'])
                delta = target_fondo - _get_fondo_cassa()
                if delta != MONEY_ZERO:
                    FondoCassaMovimento.objects.create(
                        date=timezone.localdate(),
                        importo=delta,
                        descrizione='Rettifica manuale da Impostazioni',
                    )

            return JsonResponse({
                'status': 'success',
                'data': {
                    'saldo_cassa': float(_get_saldo_cassa()),
                    'fondo_cassa': float(_get_fondo_cassa()),
                },
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_reset_telegram_sessions(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito.'}, status=405)

    reset_at = timezone.now().isoformat()
    AppSetting.objects.update_or_create(
        key='telegram_reset_sessions_at',
        defaults={'value': reset_at},
    )

    token = _get_telegram_token()
    chat_ids = _get_telegram_chat_ids()
    sent = 0
    failed = 0
    if token:
        message = (
            "myTab: eventuali sessioni Telegram rimaste in sospeso sono state azzerate.\n\n"
            "Puoi inviare nuove foto per creare una nuova bozza."
        )
        for chat_id in chat_ids:
            try:
                if _send_telegram_message(token, chat_id, message):
                    sent += 1
            except Exception:
                failed += 1

    return JsonResponse({
        'status': 'success',
        'data': {
            'reset_at': reset_at,
            'telegram_messages_sent': sent,
            'telegram_messages_failed': failed,
            'known_chats': len(chat_ids),
        },
    })


@require_admin
def api_restart_telegram_bot(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito.'}, status=405)

    restart_at = timezone.now().isoformat()
    AppSetting.objects.update_or_create(
        key='telegram_bot_restart_requested_at',
        defaults={'value': restart_at},
    )

    return JsonResponse({
        'status': 'success',
        'data': {
            'restart_requested_at': restart_at,
            'message': 'Richiesta di riavvio bot registrata.',
        },
    })


# ── ACQUISIZIONE IA (Groq — Llama 4 Scout Vision) ────────────────────────────

AI_PROMPT = """Sei un assistente per la gestione di una tabaccheria italiana.
Analizza questa immagine di un riepilogo di chiusura cassa ed estrai i dati.

Restituisci SOLO un oggetto JSON valido (nessun markdown, nessun backtick, nessun testo aggiuntivo) con questa struttura esatta:

{
  "date": "YYYY-MM-DD",
  "summary": {
    "contanti": 0.00,
    "pag_pos": 0.00,
    "cassa_auto": 0.00,
    "reso_cont": 0.00,
    "reso_auto": 0.00,
    "distrib": 0.00,
    "totale": 0.00
  },
  "items": [
    {"descrizione": "NOME REPARTO", "entrate": 0.00, "uscite": 0.00, "saldo": 0.00}
  ]
}

Regole:
- Data in formato YYYY-MM-DD
- Tutti gli importi sono numeri float (non stringhe)
- saldo = entrate - uscite (può essere negativo)
- Nomi reparto in MAIUSCOLO
- Includi TUTTI i singoli reparti visibili; escludi righe di totale/subtotale di sezione
- Mappa le colonne del summary: contanti→Contanti, pag_pos→Pag.Pos, cassa_auto→Cassa Auto,
  reso_cont→Reso Cont., reso_auto→Reso Auto, distrib→Distrib., totale→TOTALE
- Se un valore non è leggibile usa 0.00"""


def _json_from_ai_text(raw_json):
    raw_json = (raw_json or '').strip()
    if raw_json.startswith('```'):
        raw_json = raw_json.split('```')[1]
        if raw_json.startswith('json'):
            raw_json = raw_json[4:]
    start = raw_json.find('{')
    end = raw_json.rfind('}')
    if start != -1 and end != -1 and end > start:
        raw_json = raw_json[start:end + 1]
    return json.loads(raw_json)


def _parse_ai_closure_payload(parsed, totale_scassettato=None, draft_id=None, operator='IA'):
    items = []
    for item in parsed.get('items', []):
        entrate = _money(item.get('entrate'))
        uscite = _money(item.get('uscite'))
        items.append({
            'descrizione': str(item.get('descrizione', '')).strip().upper(),
            'entrate': float(entrate),
            'uscite': float(uscite),
            'saldo': float(_money(entrate - uscite)),
        })

    known = list(Department.objects.values_list('name', flat=True))
    for item in items:
        resolved = _resolve_dept(item['descrizione'], known)
        if resolved:
            item['descrizione'] = resolved

    seen: dict = {}
    for item in items:
        name = item['descrizione']
        if name not in seen:
            seen[name] = item
        elif seen[name]['entrate'] == 0 and seen[name]['uscite'] == 0:
            seen[name] = item
    items = list(seen.values())

    summary = parsed.get('summary', {})
    totale = _money(summary.get('totale'))
    pag_pos = _money(summary.get('pag_pos'))
    distrib = _money(summary.get('distrib'))
    reso_auto = _money(summary.get('reso_auto'))
    reso_cont = _money(summary.get('reso_cont'))
    cassetto = _money(totale_scassettato) if totale_scassettato is not None else MONEY_ZERO
    atteso = totale - pag_pos - distrib - reso_auto - reso_cont
    differenza = _money(cassetto - atteso) if totale_scassettato is not None else MONEY_ZERO

    data = {
        'date': parsed.get('date', ''),
        'operator': operator,
        'summary': {
            'contanti': _money_number(summary.get('contanti')),
            'pag_pos': float(pag_pos),
            'cassa_auto': _money_number(summary.get('cassa_auto')),
            'reso_cont': float(reso_cont),
            'reso_auto': float(reso_auto),
            'distrib': float(distrib),
            'totale': float(totale),
            'totale_cassetto': float(cassetto),
            'differenza': float(differenza),
        },
        'items': items,
    }
    if draft_id:
        data['draft_id'] = draft_id
    return data


def _extract_ai_with_groq(images):
    api_key = _get_groq_key()
    if not api_key:
        raise ValueError('Chiave API Groq non configurata. Vai su Impostazioni per inserirla.')

    from openai import OpenAI

    content = []
    for image in images:
        content.append({
            'type': 'image_url',
            'image_url': {'url': f"data:{image['mime']};base64,{image['b64']}"},
        })
    content.append({'type': 'text', 'text': AI_PROMPT})

    client = OpenAI(api_key=api_key, base_url='https://api.groq.com/openai/v1')
    response = client.chat.completions.create(
        model='meta-llama/llama-4-scout-17b-16e-instruct',
        max_tokens=2048,
        response_format={'type': 'json_object'},
        messages=[{'role': 'user', 'content': content}],
    )
    return _json_from_ai_text(response.choices[0].message.content)


def _extract_ai_with_gemini(images):
    api_key = _get_gemini_key()
    if not api_key:
        raise ValueError('Chiave API Gemini non configurata. Vai su Impostazioni per inserirla.')

    parts = []
    for image in images:
        parts.append({
            'inline_data': {
                'mime_type': image['mime'],
                'data': image['b64'],
            },
        })
    parts.append({'text': AI_PROMPT})

    payload = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': 0,
            'response_mime_type': 'application/json',
        },
    }
    data = json.dumps(payload).encode('utf-8')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={urllib.parse.quote(api_key)}'
    req = urllib.request.Request(
        url,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.loads(response.read().decode('utf-8'))
    raw_json = result['candidates'][0]['content']['parts'][0]['text']
    return _json_from_ai_text(raw_json)


def _extract_ai_payload(images):
    provider = _get_ai_provider()
    if provider == 'gemini':
        return _extract_ai_with_gemini(images), 'IA Gemini'
    return _extract_ai_with_groq(images), 'IA Groq'


@require_auth
def api_extract_closure_ai(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

    if not request.FILES:
        return JsonResponse({'error': 'Nessuna immagine fornita.'}, status=400)

    try:
        images = []
        for file_key in request.FILES:
            f = request.FILES[file_key]
            mime = f.content_type or 'image/jpeg'
            b64 = base64.standard_b64encode(f.read()).decode('utf-8')
            images.append({'mime': mime, 'b64': b64})

        parsed, operator = _extract_ai_payload(images)
        return JsonResponse({
            'status': 'success',
            'provider': _get_ai_provider(),
            'data': _parse_ai_closure_payload(parsed, operator=operator),
        })

    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'Risposta IA non in formato JSON valido: {e}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Errore acquisizione IA: {e}'}, status=500)


# ── BOZZE ACQUISIZIONE TELEGRAM ──────────────────────────────────────────────

@require_auth
def api_acquisition_drafts_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    drafts = AcquisitionDraft.objects.filter(status='pending').prefetch_related('images')[:20]
    return JsonResponse({
        'status': 'success',
        'data': [{
            'id': d.id,
            'source': d.source,
            'operator': d.operator,
            'totale_scassettato': float(d.totale_scassettato),
            'photo_count': d.images.count(),
            'created_at': d.created_at.isoformat(),
        } for d in drafts],
    })


@require_auth
def api_acquisition_draft_extract(request, draft_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        draft = AcquisitionDraft.objects.prefetch_related('images').get(id=draft_id, status='pending')
    except AcquisitionDraft.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Bozza non trovata'}, status=404)

    try:
        images = []
        for draft_image in draft.images.all():
            try:
                with draft_image.image.open('rb') as img:
                    b64 = base64.standard_b64encode(img.read()).decode('utf-8')
            except FileNotFoundError:
                return JsonResponse({
                    'status': 'error',
                    'error': 'Le foto di questa bozza non sono più disponibili sul server. Aggiorna myTab e fai reinviare le foto all’operatore.',
                }, status=400)
            images.append({'mime': 'image/jpeg', 'b64': b64})
        if not images:
            return JsonResponse({'status': 'error', 'error': 'Bozza senza immagini'}, status=400)

        parsed, operator = _extract_ai_payload(images)

        return JsonResponse({
            'status': 'success',
            'provider': _get_ai_provider(),
            'data': _parse_ai_closure_payload(
                parsed,
                totale_scassettato=draft.totale_scassettato,
                draft_id=draft.id,
                operator=operator,
            ),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': f'Errore estrazione bozza: {e}'}, status=500)


@require_auth
def api_acquisition_draft_cancel(request, draft_id):
    if request.method not in ['POST', 'DELETE']:
        return JsonResponse({'status': 'error'}, status=405)
    updated = AcquisitionDraft.objects.filter(id=draft_id, status='pending').update(
        status='cancelled',
        completed_at=timezone.now(),
    )
    if not updated:
        return JsonResponse({'status': 'error', 'error': 'Bozza non trovata o già registrata'}, status=404)
    return JsonResponse({'status': 'success'})


# ── VERSAMENTI ────────────────────────────────────────────────────────────────

def _get_saldo_cassa_base():
    from django.db.models import Sum
    tc   = CashClosure.objects.aggregate(s=Sum('totale_cassetto'))['s'] or 0
    diff = CashClosure.objects.aggregate(s=Sum('differenza'))['s'] or 0
    vers = Versamento.objects.aggregate(s=Sum('importo_versato'))['s'] or 0
    return _money(tc) + _money(diff) - _money(vers)


def _get_saldo_cassa():
    return _get_saldo_cassa_base() + _get_setting_money('saldo_cassa_adjustment')


@require_auth
def api_versamenti_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    items = Versamento.objects.all()
    return JsonResponse({
        'status': 'success',
        'saldo_cassa': float(_get_saldo_cassa()),
        'data': [{
            'id': v.id,
            'date': v.date.isoformat(),
            'operator': v.operator,
            'importo_versato': float(v.importo_versato),
            'accantonamento': float(v.accantonamento),
            'saldo_precedente': float(v.saldo_precedente),
            'note': v.note,
        } for v in items],
    })


@require_auth
def api_versamenti_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        date_str = data.get('date', '')
        parsed_date = parse_date(date_str)
        if not parsed_date:
            return JsonResponse({'status': 'error', 'error': 'Data non valida'})
        importo = _money(data.get('importo_versato'))
        accantonamento = _money(data.get('accantonamento'))
        if importo <= 0:
            return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
        if accantonamento < 0 or accantonamento > importo:
            return JsonResponse({'status': 'error', 'error': 'Accantonamento non valido'})
        saldo_prec = _get_saldo_cassa()
        v = Versamento.objects.create(
            date=parsed_date,
            operator=data.get('operator', ''),
            importo_versato=importo,
            accantonamento=accantonamento,
            saldo_precedente=saldo_prec,
            note=data.get('note', '').strip(),
        )
        if accantonamento > 0:
            FondoCassaMovimento.objects.create(
                date=parsed_date,
                importo=accantonamento,
                descrizione=f'Accantonamento da versamento del {parsed_date.strftime("%d/%m/%Y")} ({data.get("operator", "")})',
                versamento=v,
            )
        return JsonResponse({'status': 'success', 'id': v.id, 'saldo_precedente': float(saldo_prec)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_versamenti_delete(request, vers_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        versamento = Versamento.objects.get(id=vers_id)
        FondoCassaMovimento.objects.filter(versamento=versamento).delete()
        versamento.delete()
        return JsonResponse({'status': 'success'})
    except Versamento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)


@require_admin
def api_versamenti_update(request, vers_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        v = Versamento.objects.get(id=vers_id)
        if 'date' in data:
            parsed = parse_date(data['date'])
            if not parsed:
                return JsonResponse({'status': 'error', 'error': 'Data non valida'})
            v.date = parsed
        if 'operator' in data:
            v.operator = data['operator'].strip()
        if 'importo_versato' in data:
            importo = _money(data['importo_versato'])
            if importo <= 0:
                return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
            v.importo_versato = importo
        if 'accantonamento' in data:
            acc = _money(data['accantonamento'])
            if acc < 0:
                return JsonResponse({'status': 'error', 'error': 'Accantonamento non valido'})
            v.accantonamento = acc
        if 'note' in data:
            v.note = data['note'].strip()
        if v.accantonamento > v.importo_versato:
            return JsonResponse({'status': 'error', 'error': 'Accantonamento non valido'})
        fondo_qs = FondoCassaMovimento.objects.filter(versamento=v)
        if v.accantonamento > 0:
            descrizione = f'Accantonamento da versamento del {v.date.strftime("%d/%m/%Y")} ({v.operator})'
            if fondo_qs.exists():
                fondo_qs.update(importo=v.accantonamento, date=v.date, descrizione=descrizione)
            else:
                FondoCassaMovimento.objects.create(
                    date=v.date,
                    importo=v.accantonamento,
                    descrizione=descrizione,
                    versamento=v,
                )
        else:
            fondo_qs.delete()
        v.save()
        return JsonResponse({'status': 'success'})
    except Versamento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


# ── FONDO CASSA ───────────────────────────────────────────────────────────────

def _get_fondo_cassa():
    from django.db.models import Sum
    total = FondoCassaMovimento.objects.aggregate(s=Sum('importo'))['s'] or 0
    return _money(total)


@require_auth
def api_fondo_cassa_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    movimenti = FondoCassaMovimento.objects.select_related('versamento').all()
    return JsonResponse({
        'status': 'success',
        'totale': float(_get_fondo_cassa()),
        'data': [{
            'id': m.id,
            'date': m.date.isoformat(),
            'importo': float(m.importo),
            'descrizione': m.descrizione,
            'versamento_id': m.versamento_id,
        } for m in movimenti],
    })


@require_admin
def api_fondo_cassa_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        parsed_date = parse_date(data.get('date', ''))
        if not parsed_date:
            return JsonResponse({'status': 'error', 'error': 'Data non valida'})
        importo = _money(data.get('importo'))
        if importo == 0:
            return JsonResponse({'status': 'error', 'error': 'Importo non può essere zero'})
        m = FondoCassaMovimento.objects.create(
            date=parsed_date,
            importo=importo,
            descrizione=data.get('descrizione', '').strip(),
        )
        return JsonResponse({'status': 'success', 'id': m.id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_fondo_cassa_delete(request, mov_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        FondoCassaMovimento.objects.get(id=mov_id).delete()
        return JsonResponse({'status': 'success'})
    except FondoCassaMovimento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)


@require_admin
def api_fondo_cassa_update(request, mov_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        m = FondoCassaMovimento.objects.get(id=mov_id)
        if 'date' in data:
            parsed = parse_date(data['date'])
            if not parsed:
                return JsonResponse({'status': 'error', 'error': 'Data non valida'})
            m.date = parsed
        if 'importo' in data:
            m.importo = _money(data['importo'])
        if 'descrizione' in data:
            m.descrizione = data['descrizione'].strip()
        m.save()
        return JsonResponse({'status': 'success'})
    except FondoCassaMovimento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
