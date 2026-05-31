from __future__ import annotations

import json
import base64
import copy
import io
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.models import User
from difflib import get_close_matches
from .models import (
    AcquisitionDraft,
    AcquisitionDraftImage,
    BankTransaction,
    CashClosure,
    CashClosureImage,
    CashClosureItem,
    Company,
    Department,
    AppSetting,
    UserProfile,
    Versamento,
    MovimentoCassa,
    FondoCassaMovimento,
    PushSubscription,
)
from .nav_permissions import default_sidebar_menu, normalize_sidebar_menu
from .company_scope import (
    bind_company,
    create_company_for_user,
    ensure_user_membership,
    get_active_company,
    get_user_assigned_company,
    is_admin_user,
    provision_default_membership,
    serialize_company,
    set_active_company,
    set_user_company,
    user_companies,
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
    return is_admin_user(user)


def _get_user_sidebar_menu(user):
    is_admin = _is_admin(user)
    try:
        menu = user.profile.sidebar_menu
    except UserProfile.DoesNotExist:
        return default_sidebar_menu(is_admin)
    if menu:
        return normalize_sidebar_menu(menu, is_admin)
    return default_sidebar_menu(is_admin)


def _set_user_sidebar_menu(user, menu_ids):
    is_admin = _is_admin(user)
    normalized = normalize_sidebar_menu(menu_ids, is_admin)
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.sidebar_menu = normalized
    profile.save(update_fields=['sidebar_menu'])
    return normalized


def _user_info(user, request=None):
    info = {
        'id': user.id,
        'username': user.username,
        'role': 'amministratore' if _is_admin(user) else 'utente',
        'sidebar_menu': _get_user_sidebar_menu(user),
    }
    assigned = get_user_assigned_company(user)
    info['assigned_company'] = serialize_company(assigned)
    if request is not None:
        company = get_active_company(request)
        info['company'] = serialize_company(company)
        info['active_company_id'] = company.id if company else None
        info['can_switch_company'] = _is_admin(user)
        if _is_admin(user):
            info['companies'] = [serialize_company(c) for c in user_companies(user)]
        elif assigned:
            info['companies'] = [serialize_company(assigned)]
        else:
            info['companies'] = []
    return info

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
        get_active_company(request)
        return JsonResponse({'status': 'success', 'data': _user_info(user, request)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

def api_logout(request):
    auth_logout(request)
    return JsonResponse({'status': 'success'})

@ensure_csrf_cookie
def api_me(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    return JsonResponse({'status': 'success', 'data': _user_info(request.user, request)})


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
        if role == 'amministratore':
            set_user_company(user, None)
        else:
            company_id = data.get('company_id')
            if not company_id:
                user.delete()
                return JsonResponse({'status': 'error', 'error': 'Seleziona un\'azienda per l\'operatore'})
            try:
                company_id = int(company_id)
            except (TypeError, ValueError):
                user.delete()
                return JsonResponse({'status': 'error', 'error': 'Azienda non valida'})
            company = Company.objects.filter(id=company_id).first()
            if not company:
                user.delete()
                return JsonResponse({'status': 'error', 'error': 'Azienda non valida'})
            set_user_company(user, company)
        if 'sidebar_menu' in data:
            _set_user_sidebar_menu(user, data.get('sidebar_menu'))
        else:
            _set_user_sidebar_menu(user, default_sidebar_menu(user.is_staff))
        return JsonResponse({'status': 'success', 'data': _user_info(user, request)})
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
        was_admin = user.is_staff
        user.is_staff = role == 'amministratore'
        if password:
            user.set_password(password)
        user.save()
        if user.is_staff:
            set_user_company(user, None)
        else:
            company_id = data.get('company_id')
            if company_id:
                company = Company.objects.filter(id=int(company_id)).first()
                if not company:
                    return JsonResponse({'status': 'error', 'error': 'Azienda non valida'})
                set_user_company(user, company)
            elif not get_user_assigned_company(user):
                return JsonResponse({'status': 'error', 'error': 'Seleziona un\'azienda per l\'operatore'})
        if 'sidebar_menu' in data:
            _set_user_sidebar_menu(user, data.get('sidebar_menu'))
        elif was_admin != user.is_staff:
            _set_user_sidebar_menu(user, default_sidebar_menu(user.is_staff))
        if user.id == request.user.id and password:
            update_session_auth_hash(request, user)
        return JsonResponse({'status': 'success', 'data': _user_info(user, request)})
    except User.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Utente non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


# ── AZIENDE ───────────────────────────────────────────────────────────────────

@require_auth
def api_companies_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    companies = user_companies(request.user)
    active = get_active_company(request)
    return JsonResponse({
        'status': 'success',
        'active_company_id': active.id if active else None,
        'data': [serialize_company(c) for c in companies],
    })


@require_admin
def api_companies_switch(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body or '{}')
        company_id = data.get('company_id')
        if not company_id or not set_active_company(request, int(company_id)):
            return JsonResponse({'status': 'error', 'error': 'Azienda non valida'}, status=400)
        company = get_active_company(request)
        return JsonResponse({'status': 'success', 'data': serialize_company(company)})
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'error': 'Azienda non valida'}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_companies_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body or '{}')
        denominazione = data.get('denominazione', '').strip()
        if not denominazione:
            return JsonResponse({'status': 'error', 'error': 'Denominazione obbligatoria'})
        company = create_company_for_user(
            request.user,
            denominazione=denominazione,
            indirizzo=data.get('indirizzo', '').strip(),
            piva=data.get('piva', '').strip(),
        )
        set_active_company(request, company.id)
        return JsonResponse({
            'status': 'success',
            'data': serialize_company(company),
            'active_company_id': company.id,
            'companies': [serialize_company(c) for c in user_companies(request.user)],
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_companies_update(request, company_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        company = user_companies(request.user).filter(id=company_id).first()
        if not company:
            return JsonResponse({'status': 'error', 'error': 'Azienda non trovata'}, status=404)
        data = json.loads(request.body or '{}')
        denominazione = data.get('denominazione', '').strip()
        if not denominazione:
            return JsonResponse({'status': 'error', 'error': 'Denominazione obbligatoria'})
        company.denominazione = denominazione
        company.indirizzo = data.get('indirizzo', '').strip()
        company.piva = data.get('piva', '').strip()
        company.save()
        active = get_active_company(request)
        return JsonResponse({
            'status': 'success',
            'data': serialize_company(company),
            'active_company_id': active.id if active else None,
            'companies': [serialize_company(c) for c in user_companies(request.user)],
        })
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
    3. Fuzzy match with cutoff 0.3
    """
    name = _dept_name(name)
    if not known or not name:
        return None
    normalized_known = { _dept_name(k): _dept_name(k) for k in known if _dept_name(k) }
    if name in normalized_known:
        return normalized_known[name]
    for k in known:
        candidate = _dept_name(k)
        if len(candidate) >= 5 and (name.startswith(candidate) or candidate.startswith(name)):
            return candidate
    matches = get_close_matches(name, list(normalized_known.keys()), n=1, cutoff=0.3)
    return normalized_known[matches[0]] if matches else None


def _dept_name(value):
    return re.sub(r'\s+', ' ', str(value or '').strip()).upper()


def _department_for_import(raw_name, known_depts, company, create_missing=False):
    dept_name = _dept_name(raw_name)
    if not dept_name or dept_name == 'REPARTO SCONOSCIUTO':
        return 'REPARTO SCONOSCIUTO'

    resolved = _resolve_dept(dept_name, known_depts)
    if resolved:
        return resolved

    if create_missing:
        Department.objects.get_or_create(company=company, name=dept_name)
        known_depts.append(dept_name)
    return dept_name


def _copy_draft_images_to_closure(draft, closure):
    for index, draft_image in enumerate(draft.images.all(), start=1):
        try:
            with draft_image.image.open('rb') as img:
                image_bytes = img.read()
        except FileNotFoundError:
            continue
        name = os.path.basename(draft_image.image.name) or f'draft_{draft.id}_{index}.jpg'
        CashClosureImage.objects.create(
            closure=closure,
            source=draft.source,
            image=ContentFile(image_bytes, name=name),
        )
        draft_image.image.delete(save=False)
        draft_image.delete()


def _create_upload_draft(request, company, source='web'):
    draft = AcquisitionDraft.objects.create(
        company=company,
        source=source,
        operator=request.user.username,
    )
    for index, file_key in enumerate(request.FILES, start=1):
        uploaded = request.FILES[file_key]
        AcquisitionDraftImage.objects.create(
            draft=draft,
            image=ContentFile(uploaded.read(), name=f'{source}_{request.user.id}_{draft.id}_{index}_{uploaded.name}'),
        )
    return draft


@require_auth
def api_insert_closure(request):
    if request.method == 'POST':
        company, err = bind_company(request)
        if err:
            return err
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
                    draft = AcquisitionDraft.objects.prefetch_related('images').filter(id=draft_id, company=company, status='pending').first()

                # Inserimento Master
                closure = CashClosure.objects.create(
                    company=company,
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
                known_depts = list(Department.objects.filter(company=company).values_list('name', flat=True))
                for item in items:
                    dept_name = _department_for_import(
                        item.get('descrizione', ''),
                        known_depts,
                        company,
                        create_missing=True,
                    )

                    CashClosureItem.objects.create(
                        closure=closure,
                        department_name=dept_name,
                        incomes=_money(item.get('entrate')),
                        expenses=abs(_money(item.get('uscite'))),
                        balance=_money(_money(item.get('entrate')) - abs(_money(item.get('uscite'))))
                    )

                if draft:
                    _copy_draft_images_to_closure(draft, closure)
                    AcquisitionDraft.objects.filter(id=draft.id, status='pending').update(
                        status='completed',
                        completed_at=timezone.now(),
                    )

            push_sent = 0
            push_devices = 0
            try:
                from .draft_notifications import notify_closure_saved, push_subscriptions_for_company
                push_devices = push_subscriptions_for_company(company).count()
                push_sent = notify_closure_saved(company, closure, items, summary, operator)
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Push riepilogo chiusura non inviata')

            return JsonResponse({
                'status': 'success', 
                'message': f'Chiusura cassa inserita correttamente con {len(items)} voci.',
                'id': closure.id,
                'push_sent': push_sent,
                'push_devices': push_devices,
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'JSON non valido'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

@require_admin
def api_extract_closure(request):
    if request.method == 'POST':
        company, err = bind_company(request)
        if err:
            return err
        if not request.FILES:
            return JsonResponse({'error': 'Nessuna immagine fornita.'}, status=400)
            
        try:
            full_text = ""
            draft = AcquisitionDraft.objects.create(company=company, source='web', operator=request.user.username)
            for file_key in request.FILES:
                uploaded = request.FILES[file_key]
                file_bytes = uploaded.read()
                AcquisitionDraftImage.objects.create(
                    draft=draft,
                    image=ContentFile(file_bytes, name=f'web_{request.user.id}_{draft.id}_{file_key}_{uploaded.name}'),
                )
                img = Image.open(io.BytesIO(file_bytes))
                img = _preprocess(img)
                full_text += pytesseract.image_to_string(img, lang='ita', config='--psm 6') + "\n"

            parsed_data = parse_closure_receipt(full_text)
            date_str = parsed_data['date'].isoformat() if parsed_data['date'] else ""

            # Risolve nomi reparti contro archivio (exact → prefix → fuzzy)
            known = list(Department.objects.filter(company=company).values_list('name', flat=True))
            for item in parsed_data['items']:
                resolved = _resolve_dept(item['descrizione'], known)
                if resolved:
                    item['descrizione'] = resolved
                else:
                    item['descrizione'] = _dept_name(item['descrizione'])

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
                'draft_id': draft.id,
                'images': [{
                    'id': image.id,
                    'url': f'/api/acquisition-draft-images/{image.id}/view/',
                } for image in draft.images.all()],
            }

            return JsonResponse({'status': 'success', 'data': response_data})

        except Exception as e:
            return JsonResponse({'error': f"Errore elaborazione immagine: {str(e)}"}, status=500)

    return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

@require_admin
def api_list_closures(request):
    if request.method == 'GET':
        company, err = bind_company(request)
        if err:
            return err
        closures = CashClosure.objects.filter(company=company).prefetch_related('items', 'images')
        data = []
        for c in closures:
            items = []
            for item in c.items.all():
                items.append({
                    'id': item.id,
                    'descrizione': _dept_name(item.department_name),
                    'entrate': float(item.incomes),
                    'uscite': float(item.expenses),
                    'saldo': float(item.balance)
                })
            
            data.append({
                'id': c.id,
                'date': c.date.isoformat(),
                'operator': c.operator,
                'submitted_by': c.submitted_by,
                'image_count': c.images.count(),
                'images': [{
                    'id': image.id,
                    'url': f'/api/closure-images/{image.id}/view/',
                    'source': image.source,
                    'created_at': image.created_at.isoformat(),
                } for image in c.images.all()],
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
            company, err = bind_company(request)
            if err:
                return err
            closure = CashClosure.objects.get(id=closure_id, company=company)
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
                        if 'descrizione' in item_data: item.department_name = _dept_name(item_data['descrizione'])
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
            company, err = bind_company(request)
            if err:
                return err
            closure = CashClosure.objects.get(id=closure_id, company=company)
            for image in closure.images.all():
                image.image.delete(save=False)
            closure.delete()
            return JsonResponse({'status': 'success', 'message': 'Chiusura eliminata correttamente.'})
        except CashClosure.DoesNotExist:
            return JsonResponse({'error': 'Chiusura non trovata'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
            
    return JsonResponse({'error': 'Metodo non consentito. Usa DELETE.'}, status=405)


@require_auth
def api_closure_image_view(request, image_id):
    company, err = bind_company(request)
    if err:
        return err
    try:
        image = CashClosureImage.objects.get(id=image_id, closure__company=company)
    except CashClosureImage.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Immagine non trovata'}, status=404)
    return FileResponse(image.image.open('rb'))


@require_auth
def api_closure_images_upload(request, closure_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        closure = CashClosure.objects.get(id=closure_id, company=company)
    except CashClosure.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Chiusura non trovata'}, status=404)
    if not request.FILES:
        return JsonResponse({'status': 'error', 'error': 'Nessuna immagine fornita'}, status=400)

    created = []
    for file_key in request.FILES:
        uploaded = request.FILES[file_key]
        img = CashClosureImage.objects.create(
            closure=closure,
            source='manuale',
            image=uploaded,
        )
        created.append({
            'id': img.id,
            'url': f'/api/closure-images/{img.id}/view/',
            'source': img.source,
            'created_at': img.created_at.isoformat(),
        })
    return JsonResponse({'status': 'success', 'data': created})


@require_auth
def api_closure_image_delete(request, image_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        image = CashClosureImage.objects.get(id=image_id, closure__company=company)
    except CashClosureImage.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Immagine non trovata'}, status=404)
    image.image.delete(save=False)
    image.delete()
    return JsonResponse({'status': 'success'})


@require_auth
def api_acquisition_draft_image_view(request, image_id):
    company, err = bind_company(request)
    if err:
        return err
    try:
        image = AcquisitionDraftImage.objects.get(id=image_id, draft__company=company, draft__status='pending')
    except AcquisitionDraftImage.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Immagine bozza non trovata'}, status=404)
    return FileResponse(image.image.open('rb'))


# ── REPARTI ──────────────────────────────────────────────────────────────────

@require_admin
def api_list_departments(request):
    if request.method == 'GET':
        company, err = bind_company(request)
        if err:
            return err
        data = [{'id': d.id, 'name': _dept_name(d.name)} for d in Department.objects.filter(company=company)]
        return JsonResponse({'status': 'success', 'data': data})
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_create_department(request):
    if request.method == 'POST':
        try:
            name = _dept_name(json.loads(request.body).get('name', ''))
            if not name:
                return JsonResponse({'error': 'Nome obbligatorio.'}, status=400)
            company, err = bind_company(request)
            if err:
                return err
            dept, created = Department.objects.get_or_create(company=company, name=name)
            return JsonResponse({'status': 'success', 'id': dept.id, 'name': dept.name},
                                status=201 if created else 200)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_update_department(request, dept_id):
    if request.method in ['POST', 'PUT']:
        try:
            company, err = bind_company(request)
            if err:
                return err
            dept = Department.objects.get(id=dept_id, company=company)
            name = _dept_name(json.loads(request.body).get('name', ''))
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
            company, err = bind_company(request)
            if err:
                return err
            Department.objects.get(id=dept_id, company=company).delete()
            return JsonResponse({'status': 'success'})
        except Department.DoesNotExist:
            return JsonResponse({'error': 'Reparto non trovato.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


# ── IMPOSTAZIONI ─────────────────────────────────────────────────────────────

GLOBAL_API_SETTING_KEYS = ('groq_api_key', 'gemini_api_key')


def _get_global_setting(key):
    env_map = {
        'groq_api_key': 'GROQ_API_KEY',
        'gemini_api_key': 'GEMINI_API_KEY',
    }
    env_val = os.environ.get(env_map.get(key, ''), '').strip()
    if env_val:
        return env_val
    row = AppSetting.objects.filter(key=key).exclude(value='').order_by('id').first()
    return row.value.strip() if row else ''


def _set_global_setting(key, value):
    value = (value or '').strip()
    for company in Company.objects.all():
        AppSetting.objects.update_or_create(
            company=company,
            key=key,
            defaults={'value': value},
        )


def _get_groq_key(company=None):
    return _get_global_setting('groq_api_key')


def _get_gemini_key(company=None):
    return _get_global_setting('gemini_api_key')


def _get_ai_provider(company):
    try:
        provider = AppSetting.objects.get(company=company, key='ai_acquisition_provider').value.strip().lower()
    except AppSetting.DoesNotExist:
        provider = ''
    return provider if provider in {'groq', 'gemini'} else 'groq'


def _get_user_ai_provider(user):
    try:
        provider = user.profile.ai_acquisition_provider.strip().lower()
    except UserProfile.DoesNotExist:
        provider = ''
    return provider if provider in {'groq', 'gemini'} else ''


def _set_user_ai_provider(user, provider):
    provider = str(provider or '').strip().lower()
    if provider not in {'groq', 'gemini'}:
        raise ValueError('Provider IA non valido.')
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.ai_acquisition_provider = provider
    profile.save(update_fields=['ai_acquisition_provider'])


def _resolve_ai_provider(user, company=None, override=None):
    chosen = str(override or '').strip().lower()
    if chosen in {'groq', 'gemini'}:
        return chosen
    user_pref = _get_user_ai_provider(user)
    if user_pref:
        return user_pref
    return 'groq'


def _ai_provider_options(user, company=None):
    return {
        'provider': _resolve_ai_provider(user, company),
        'user_provider': _get_user_ai_provider(user) or None,
        'groq_configured': bool(_get_groq_key()),
        'gemini_configured': bool(_get_gemini_key()),
    }


def _is_rate_limit_error(exc):
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        return True
    msg = str(exc).lower()
    return '429' in msg or 'too many requests' in msg or 'rate limit' in msg


def _rate_limit_message(provider):
    alt = 'Gemini' if provider == 'groq' else 'Groq'
    return (
        f'Limite richieste del servizio {provider.upper()} (errore 429). '
        f'Attendi uno o due minuti oppure vai in Impostazioni e seleziona {alt} come tuo modello IA.'
    )


def _set_ai_provider(company, provider):
    provider = str(provider or '').strip().lower()
    if provider not in {'groq', 'gemini'}:
        raise ValueError('Provider IA non valido.')
    AppSetting.objects.update_or_create(
        company=company,
        key='ai_acquisition_provider',
        defaults={'value': provider},
    )


def _get_telegram_token(company):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        try:
            token = AppSetting.objects.get(company=company, key='telegram_bot_token').value.strip()
        except AppSetting.DoesNotExist:
            pass
    return token


def _get_setting_money(key, company):
    try:
        return _money(AppSetting.objects.get(company=company, key=key).value)
    except AppSetting.DoesNotExist:
        return MONEY_ZERO


def _set_setting_money(key, value, company):
    AppSetting.objects.update_or_create(
        company=company,
        key=key,
        defaults={'value': str(_money(value))},
    )


def _get_telegram_chat_ids(company):
    chat_ids = set(
        AcquisitionDraft.objects
        .filter(company=company)
        .exclude(telegram_chat_id='')
        .values_list('telegram_chat_id', flat=True)
    )
    try:
        raw = AppSetting.objects.get(company=company, key='telegram_chat_ids').value
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


def _delete_image_objects(images):
    count = 0
    for image in list(images):
        image.image.delete(save=False)
        image.delete()
        count += 1
    return count


@require_admin
def api_get_settings(request):
    if request.method == 'GET':
        company, err = bind_company(request)
        if err:
            return err
        return JsonResponse({
            'status': 'success',
            'data': {
                'groq_key_configured': bool(_get_groq_key(company)),
                'gemini_key_configured': bool(_get_gemini_key(company)),
                'ai_acquisition_provider': _resolve_ai_provider(request.user, company),
                'telegram_token_configured': bool(_get_telegram_token(company)),
                'saldo_cassa': float(_get_saldo_cassa(company)),
                'fondo_cassa': float(_get_fondo_cassa(company)),
                'denominazione': company.denominazione,
                'indirizzo': company.indirizzo,
                'piva': company.piva,
                'active_company_id': company.id,
                'companies': [serialize_company(c) for c in user_companies(request.user)],
            },
        })
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_save_settings(request):
    if request.method == 'POST':
        company, err = bind_company(request)
        if err:
            return err
        try:
            data = json.loads(request.body)
            key = data.get('groq_api_key', '').strip()
            if key:
                _set_global_setting('groq_api_key', key)

            gemini_key = data.get('gemini_api_key', '').strip()
            if gemini_key:
                _set_global_setting('gemini_api_key', gemini_key)

            telegram_token = data.get('telegram_bot_token', '').strip()
            if telegram_token:
                AppSetting.objects.update_or_create(
                    company=company,
                    key='telegram_bot_token',
                    defaults={'value': telegram_token},
                )

            if 'saldo_cassa' in data:
                target_saldo = _money(data['saldo_cassa'])
                _set_setting_money('saldo_cassa_adjustment', target_saldo - _get_saldo_cassa_base(company), company)

            if any(k in data for k in ('denominazione', 'indirizzo', 'piva')):
                if 'denominazione' in data:
                    denominazione = data.get('denominazione', '').strip()
                    if not denominazione:
                        return JsonResponse({'error': 'Denominazione obbligatoria'}, status=400)
                    company.denominazione = denominazione
                if 'indirizzo' in data:
                    company.indirizzo = data.get('indirizzo', '').strip()
                if 'piva' in data:
                    company.piva = data.get('piva', '').strip()
                company.save()

            if 'fondo_cassa' in data:
                target_fondo = _money(data['fondo_cassa'])
                delta = target_fondo - _get_fondo_cassa(company)
                if delta != MONEY_ZERO:
                    FondoCassaMovimento.objects.create(
                        company=company,
                        date=timezone.localdate(),
                        tipo=FondoCassaMovimento.TIPO_ENTRATA if delta > 0 else FondoCassaMovimento.TIPO_USCITA,
                        importo=abs(delta),
                        descrizione='Rettifica manuale da Impostazioni',
                    )

            return JsonResponse({
                'status': 'success',
                'data': {
                    'saldo_cassa': float(_get_saldo_cassa(company)),
                    'fondo_cassa': float(_get_fondo_cassa(company)),
                    'denominazione': company.denominazione,
                    'indirizzo': company.indirizzo,
                    'piva': company.piva,
                    'active_company_id': company.id,
                    'companies': [serialize_company(c) for c in user_companies(request.user)],
                },
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@require_admin
def api_reset_telegram_sessions(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito.'}, status=405)

    company, err = bind_company(request)
    if err:
        return err

    reset_at = timezone.now().isoformat()
    AppSetting.objects.update_or_create(
        company=company,
        key='telegram_reset_sessions_at',
        defaults={'value': reset_at},
    )

    token = _get_telegram_token(company)
    chat_ids = _get_telegram_chat_ids(company)
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

    company, err = bind_company(request)
    if err:
        return err

    restart_at = timezone.now().isoformat()
    AppSetting.objects.update_or_create(
        company=company,
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


@require_admin
def api_purge_images(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito.'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        data = json.loads(request.body or '{}')
        scope = data.get('scope', 'month')
        month = data.get('month', '')

        closure_images = CashClosureImage.objects.filter(closure__company=company)
        draft_images = AcquisitionDraftImage.objects.filter(draft__company=company)

        if scope == 'month':
            if not re.fullmatch(r'\d{4}-\d{2}', month):
                return JsonResponse({'status': 'error', 'error': 'Mese non valido. Usa YYYY-MM.'}, status=400)
            year, month_num = [int(part) for part in month.split('-')]
            closure_images = closure_images.filter(created_at__year=year, created_at__month=month_num)
            draft_images = draft_images.filter(created_at__year=year, created_at__month=month_num)
        elif scope != 'all':
            return JsonResponse({'status': 'error', 'error': 'Ambito eliminazione non valido.'}, status=400)

        closure_count = _delete_image_objects(closure_images)
        draft_ids = list(draft_images.values_list('draft_id', flat=True).distinct())
        draft_count = _delete_image_objects(draft_images)
        if draft_ids:
            AcquisitionDraft.objects.filter(id__in=draft_ids, status='pending').update(
                status='cancelled',
                completed_at=timezone.now(),
            )

        return JsonResponse({
            'status': 'success',
            'data': {
                'closure_images_deleted': closure_count,
                'draft_images_deleted': draft_count,
                'total_deleted': closure_count + draft_count,
            },
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_purge_company_data(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito.'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        data = json.loads(request.body or '{}')
        confirm_name = str(data.get('confirm_company_name', '')).strip()
        if confirm_name.lower() != (company.denominazione or '').strip().lower():
            return JsonResponse({
                'status': 'error',
                'error': f'Conferma non valida. Inserisci esattamente "{company.denominazione}".',
            }, status=400)

        closure_images = CashClosureImage.objects.filter(closure__company=company)
        draft_images = AcquisitionDraftImage.objects.filter(draft__company=company)
        deleted_closure_images = _delete_image_objects(closure_images)
        deleted_draft_images = _delete_image_objects(draft_images)

        stats = {
            'closures_deleted': CashClosure.objects.filter(company=company).count(),
            'drafts_deleted': AcquisitionDraft.objects.filter(company=company).count(),
            'departments_deleted': Department.objects.filter(company=company).count(),
            'versamenti_deleted': Versamento.objects.filter(company=company).count(),
            'movimenti_deleted': MovimentoCassa.objects.filter(company=company).count(),
            'fondo_movimenti_deleted': FondoCassaMovimento.objects.filter(company=company).count(),
            'bank_transactions_deleted': BankTransaction.objects.filter(company=company).count(),
            'settings_deleted': AppSetting.objects.filter(company=company).count(),
            'closure_images_deleted': deleted_closure_images,
            'draft_images_deleted': deleted_draft_images,
        }

        with transaction.atomic():
            CashClosure.objects.filter(company=company).delete()
            AcquisitionDraft.objects.filter(company=company).delete()
            Department.objects.filter(company=company).delete()
            Versamento.objects.filter(company=company).delete()
            MovimentoCassa.objects.filter(company=company).delete()
            FondoCassaMovimento.objects.filter(company=company).delete()
            BankTransaction.objects.filter(company=company).delete()
            AppSetting.objects.filter(company=company).delete()

        return JsonResponse({
            'status': 'success',
            'data': {
                'company_id': company.id,
                'company_name': company.denominazione,
                **stats,
            },
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


# ── ACQUISIZIONE IA (Groq — Llama 4 Scout Vision) ────────────────────────────

MAIN_CLOSURE_AI_PROMPT = """Sei un assistente per la gestione di una tabaccheria italiana.
Analizza queste immagini del RIEPILOGO CHIUSURA CASSA (POS) ed estrai i dati.

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
- Data in formato YYYY-MM-DD.
- Tutti gli importi sono numeri float (non stringhe).
- "entrate" e "uscite" devono essere sempre importi positivi o 0. Non mettere mai il segno meno nella colonna "uscite".
- saldo = entrate - uscite (può essere negativo).
- Nomi reparto in MAIUSCOLO.
- Queste immagini sono SOLO il foglio riepilogo cassa (non i report Lottomatica/Sisal/Gratta separati).
- Per LOTTOMATICA e SISAL: se compaiono solo come totali di servizio, metti 0.00 (verranno dai report dedicati).
- Per GRATTA E VINCI: includi sempre la riga con le Entrate del riepilogo (colonna Entrate); le Uscite
  verranno dal report premi separato.
- Unisci le righe reparto visibili senza duplicarle.
- Includi in "items" TUTTE le righe della tabella reparti con descrizione e importi (anche solo entrate o solo uscite).
  Non omettere nessun reparto: Tabacchi, Caffè, Pasticceria, Bibite, Rosticceria, Pastigliaggi, Cartine,
  Valori bollati, Sigarette elettroniche, Gratta e Vinci, Pag fornitori, Altre uscite, Lottomatica, Mooney, Sisal, ecc.
- Includi anche la sezione "NUOVA SEZIONE GESTORI DI GIOCHI E SERVIZI" (Lottomatica, Mooney, Sisal).
- NON usare la colonna "Reparto" come filtro: il codice reparto può mancare. Righe come
  "VECCHIA GESTIONE GESTORI DI GIOCHI E SERVIZI" e "SISAL" vanno incluse se hanno importi.
- Includi anche righe con uscite e saldo negativo, ad esempio "ALTRE USCITE".
- Escludi solo intestazioni, righe vuote, note, piè pagina e il riepilogo finale con Contanti/Pag.Pos/Cassa Auto/Resi/Distrib./TOTALE.
- Mappa le colonne del summary: contanti→Contanti, pag_pos→Pag.Pos, cassa_auto→Cassa Auto,
  reso_cont→Reso Cont., reso_auto→Reso Auto, distrib→Distrib., totale→TOTALE.
- "totale" è SEMPRE l'ultima colonna della riga riepilogo in fondo (etichetta TOTALE), mai Pag.Pos,
  mai Contanti, mai il totale scassettato, mai la somma parziale di un reparto.
- La riga riepilogo ha 7 valori: Contanti, Pag.Pos, Cassa Auto, Reso Cont., Reso Auto, Distrib., TOTALE.
- Se un valore non è leggibile usa 0.00."""

# Retrocompatibilità
AI_PROMPT = MAIN_CLOSURE_AI_PROMPT


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


def _amounts_close(a, b, tol=Decimal('1.00')):
    return abs(_money(a) - _money(b)) <= tol


def _saldo_reparti(items):
    return sum(
        (_money(it.get('entrate')) - _money(it.get('uscite')) for it in (items or [])),
        MONEY_ZERO,
    )


def _reconcile_totale_cassa(summary, items, pag_pos_override=None):
    """Corregge errori IA frequenti: totale=0, totale=Pag.Pos o totale=Contanti."""
    summary = summary or {}
    totale = _money(summary.get('totale'))
    contanti = _money(summary.get('contanti'))
    pag_pos = _money(pag_pos_override if pag_pos_override is not None else summary.get('pag_pos'))
    cassa_auto = _money(summary.get('cassa_auto'))
    reso_cont = _money(summary.get('reso_cont'))
    reso_auto = _money(summary.get('reso_auto'))
    distrib = _money(summary.get('distrib'))

    footer_sum = contanti + pag_pos + cassa_auto + reso_cont + reso_auto + distrib
    saldo_reparti = _saldo_reparti(items)

    if totale <= 0:
        if footer_sum > 0 and (saldo_reparti <= 0 or _amounts_close(footer_sum, saldo_reparti)):
            return footer_sum
        if saldo_reparti > 0:
            return saldo_reparti
        return footer_sum if footer_sum > 0 else MONEY_ZERO

    if _amounts_close(totale, pag_pos) and saldo_reparti > totale + Decimal('1'):
        if _amounts_close(saldo_reparti, footer_sum) and saldo_reparti > totale:
            return saldo_reparti
        if footer_sum > totale:
            return footer_sum

    if _amounts_close(totale, contanti) and saldo_reparti > totale + Decimal('1'):
        if _amounts_close(saldo_reparti, footer_sum):
            return saldo_reparti
        if footer_sum > totale:
            return footer_sum

    if saldo_reparti > totale + Decimal('5') and _amounts_close(saldo_reparti, footer_sum):
        return saldo_reparti

    return totale


def _calc_closure_differenza(totale, pag_pos, distrib, reso_auto, reso_cont, items, with_reports, totale_scassettato=None):
    if with_reports:
        return _money(totale - _saldo_reparti(items)), MONEY_ZERO
    cassetto = _money(totale_scassettato) if totale_scassettato is not None else MONEY_ZERO
    atteso = totale - pag_pos - distrib - reso_auto - reso_cont
    differenza = _money(cassetto - atteso) if totale_scassettato is not None else MONEY_ZERO
    return differenza, cassetto


def _refresh_draft_extract_payload(draft, payload):
    """Ricalcola totale/differenza su payload memorizzato (fix anche bozze già in cache)."""
    payload = copy.deepcopy(payload)
    items = payload.get('items', [])
    summary = payload.get('summary', {})
    with_reports = bool(payload.get('with_reports'))
    pag_pos_override = None
    if draft.pag_pos_reale and float(draft.pag_pos_reale) > 0:
        pag_pos_override = float(draft.pag_pos_reale)

    totale = _reconcile_totale_cassa(summary, items, pag_pos_override=pag_pos_override)
    pag_pos = _money(pag_pos_override) if pag_pos_override is not None else _money(summary.get('pag_pos'))
    distrib = _money(summary.get('distrib'))
    reso_auto = _money(summary.get('reso_auto'))
    reso_cont = _money(summary.get('reso_cont'))
    differenza, cassetto = _calc_closure_differenza(
        totale, pag_pos, distrib, reso_auto, reso_cont, items, with_reports, draft.totale_scassettato,
    )
    payload['summary'] = {
        **summary,
        'contanti': _money_number(summary.get('contanti')),
        'pag_pos': float(pag_pos),
        'cassa_auto': _money_number(summary.get('cassa_auto')),
        'reso_cont': float(reso_cont),
        'reso_auto': float(reso_auto),
        'distrib': float(distrib),
        'totale': float(totale),
        'totale_cassetto': float(cassetto),
        'differenza': float(differenza),
    }
    return payload


def _parse_ai_closure_payload(
    parsed,
    company,
    totale_scassettato=None,
    draft_id=None,
    operator='IA',
    report_overlays=None,
    with_reports=False,
    pag_pos_override=None,
):
    items = []
    for item in parsed.get('items', []):
        entrate = _money(item.get('entrate'))
        uscite = abs(_money(item.get('uscite')))
        items.append({
            'descrizione': _dept_name(item.get('descrizione', '')),
            'entrate': float(entrate),
            'uscite': float(uscite),
            'saldo': float(_money(entrate - uscite)),
        })

    known = list(Department.objects.filter(company=company).values_list('name', flat=True))
    for item in items:
        resolved = _resolve_dept(item['descrizione'], known)
        if resolved:
            item['descrizione'] = resolved
        else:
            item['descrizione'] = _dept_name(item['descrizione'])

    seen: dict = {}
    for item in items:
        name = item['descrizione']
        if not name or name == 'REPARTO SCONOSCIUTO':
            continue
        if name not in seen:
            seen[name] = item
        else:
            prev = seen[name]
            prev_score = prev['entrate'] + prev['uscite']
            new_score = item['entrate'] + item['uscite']
            if new_score > prev_score:
                seen[name] = item
    items = list(seen.values())

    if report_overlays:
        from .ai_acquisition import merge_report_overlays_into_items
        items = merge_report_overlays_into_items(items, report_overlays)

    summary = parsed.get('summary', {})
    if pag_pos_override is not None:
        pag_pos = _money(pag_pos_override)
    else:
        pag_pos = _money(summary.get('pag_pos'))
    distrib = _money(summary.get('distrib'))
    reso_auto = _money(summary.get('reso_auto'))
    reso_cont = _money(summary.get('reso_cont'))
    totale = _reconcile_totale_cassa(summary, items, pag_pos_override=pag_pos_override)
    differenza, cassetto = _calc_closure_differenza(
        totale, pag_pos, distrib, reso_auto, reso_cont, items, with_reports, totale_scassettato,
    )

    data = {
        'date': parsed.get('date', ''),
        'operator': operator,
        'with_reports': bool(with_reports),
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


def _extract_ai_with_groq(images, company=None, prompt=None):
    api_key = _get_groq_key()
    if not api_key:
        raise ValueError('Chiave API Groq non configurata. Chiedi all\'amministratore di inserirla in Impostazioni.')

    from openai import OpenAI

    text_prompt = prompt or MAIN_CLOSURE_AI_PROMPT
    content = []
    for image in images:
        content.append({
            'type': 'image_url',
            'image_url': {'url': f"data:{image['mime']};base64,{image['b64']}"},
        })
    content.append({'type': 'text', 'text': text_prompt})

    client = OpenAI(api_key=api_key, base_url='https://api.groq.com/openai/v1')
    last_exc = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model='meta-llama/llama-4-scout-17b-16e-instruct',
                max_tokens=4096,
                response_format={'type': 'json_object'},
                messages=[{'role': 'user', 'content': content}],
            )
            return _json_from_ai_text(response.choices[0].message.content)
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_exc


def _extract_ai_with_gemini(images, company=None, prompt=None):
    api_key = _get_gemini_key()
    if not api_key:
        raise ValueError('Chiave API Gemini non configurata. Chiedi all\'amministratore di inserirla in Impostazioni.')

    text_prompt = prompt or MAIN_CLOSURE_AI_PROMPT
    parts = []
    for image in images:
        parts.append({
            'inline_data': {
                'mime_type': image['mime'],
                'data': image['b64'],
            },
        })
    parts.append({'text': text_prompt})

    payload = {
        'contents': [{'role': 'user', 'parts': parts}],
        'generationConfig': {
            'temperature': 0,
            'response_mime_type': 'application/json',
        },
    }
    data = json.dumps(payload).encode('utf-8')
    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={urllib.parse.quote(api_key)}'
    last_exc = None
    for attempt in range(3):
        req = urllib.request.Request(
            url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
            raw_json = result['candidates'][0]['content']['parts'][0]['text']
            return _json_from_ai_text(raw_json)
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429 and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as exc:
            last_exc = exc
            if _is_rate_limit_error(exc) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_exc


def _extract_ai_json(images, company, provider, prompt):
    chosen = provider or 'groq'
    if chosen == 'gemini':
        return _extract_ai_with_gemini(images, company, prompt=prompt)
    return _extract_ai_with_groq(images, company, prompt=prompt)


def _extract_report_overlays(report_slots, company, provider):
    from .ai_acquisition import REPORT_PROMPTS, normalize_report_overlay

    overlays = {}
    for key, image in report_slots.items():
        prompt = REPORT_PROMPTS.get(key)
        if not prompt or not image:
            continue
        try:
            parsed = _extract_ai_json([image], company, provider, prompt)
            normalized = normalize_report_overlay(key, parsed)
            if normalized:
                overlays[key] = normalized
        except Exception:
            continue
    return overlays


def _classify_acquisition_image(image, company, provider):
    from .ai_acquisition import CLASSIFY_PROMPT, normalize_image_type

    try:
        parsed = _extract_ai_json([image], company, provider, CLASSIFY_PROMPT)
        return normalize_image_type(parsed.get('type'))
    except Exception:
        return 'other'


def _extract_closure_with_reports(images, company, provider):
    from .ai_acquisition import split_acquisition_images

    operator_label = 'IA Gemini' if provider == 'gemini' else 'IA Groq'

    image_types = []
    if len(images) >= 3:
        image_types = [_classify_acquisition_image(img, company, provider) for img in images]

    main_images, report_slots = split_acquisition_images(images, image_types or None)

    if main_images:
        parsed = _extract_ai_json(main_images, company, provider, MAIN_CLOSURE_AI_PROMPT)
    elif report_slots:
        parsed = {'date': '', 'summary': {}, 'items': []}
    else:
        parsed = _extract_ai_json(images, company, provider, MAIN_CLOSURE_AI_PROMPT)

    overlays = _extract_report_overlays(report_slots, company, provider) if report_slots else {}
    parsed['image_types'] = image_types
    has_reports = bool(report_slots)
    return parsed, operator_label, overlays, has_reports


def _extract_ai_payload(images, company, provider=None):
    parsed, operator, _overlays, _has_reports = _extract_closure_with_reports(images, company, provider)
    return parsed, operator


def _sort_upload_file_keys(file_keys):
    def order_key(name):
        match = re.search(r'(\d+)', name or '')
        return int(match.group(1)) if match else 0
    return sorted(file_keys, key=order_key)


@require_auth
def api_acquisition_ai_provider(request):
    """Preferenza modello IA per l'operatore (persiste tra le acquisizioni)."""
    company, err = bind_company(request)
    if err:
        return err

    if request.method == 'GET':
        return JsonResponse({'status': 'success', 'data': _ai_provider_options(request.user, company)})

    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
        provider = str(data.get('ai_acquisition_provider', '')).strip().lower()
        if provider not in {'groq', 'gemini'}:
            return JsonResponse({'status': 'error', 'error': 'Modello non valido'}, status=400)
        try:
            _set_user_ai_provider(request.user, provider)
        except ValueError as exc:
            return JsonResponse({'status': 'error', 'error': str(exc)}, status=400)
        return JsonResponse({'status': 'success', 'data': _ai_provider_options(request.user, company)})

    return JsonResponse({'status': 'error', 'error': 'Metodo non consentito'}, status=405)


@require_auth
def api_extract_closure_ai(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

    company, err = bind_company(request)
    if err:
        return err

    if not request.FILES:
        return JsonResponse({'error': 'Nessuna immagine fornita.'}, status=400)

    try:
        images = []
        draft = AcquisitionDraft.objects.create(company=company, source='web', operator=request.user.username)
        for file_key in _sort_upload_file_keys(request.FILES.keys()):
            f = request.FILES[file_key]
            mime = f.content_type or 'image/jpeg'
            file_bytes = f.read()
            AcquisitionDraftImage.objects.create(
                draft=draft,
                image=ContentFile(file_bytes, name=f'web_{request.user.id}_{draft.id}_{file_key}_{f.name}'),
            )
            b64 = base64.standard_b64encode(file_bytes).decode('utf-8')
            images.append({'mime': mime, 'b64': b64})

        provider = _resolve_ai_provider(request.user, company)
        if provider == 'gemini' and not _get_gemini_key():
            return JsonResponse({'error': 'Chiave API Gemini non configurata. Chiedi all\'amministratore.'}, status=400)
        if provider == 'groq' and not _get_groq_key():
            return JsonResponse({'error': 'Chiave API Groq non configurata. Chiedi all\'amministratore.'}, status=400)

        parsed, operator, report_overlays, has_reports = _extract_closure_with_reports(images, company, provider)
        data = _parse_ai_closure_payload(
            parsed, company, operator=operator, report_overlays=report_overlays,
            with_reports=has_reports,
        )
        if report_overlays:
            data['report_overlays_applied'] = list(report_overlays.keys())
        data['draft_id'] = draft.id
        data['images'] = [{
            'id': image.id,
            'url': f'/api/acquisition-draft-images/{image.id}/view/',
        } for image in draft.images.all()]
        return JsonResponse({
            'status': 'success',
            'provider': provider,
            'data': data,
        })

    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'Risposta IA non in formato JSON valido: {e}'}, status=500)
    except Exception as e:
        provider = _resolve_ai_provider(request.user, company) if request.user.is_authenticated else 'groq'
        if _is_rate_limit_error(e):
            return JsonResponse({'error': _rate_limit_message(provider)}, status=429)
        return JsonResponse({'error': f'Errore acquisizione IA: {e}'}, status=500)


# ── BOZZE ACQUISIZIONE TELEGRAM ──────────────────────────────────────────────

# ── WEB PUSH + BOZZE TELEGRAM ────────────────────────────────────────────────

def _user_can_receive_push(user, company):
    if not user.is_authenticated or not company:
        return False
    if is_admin_user(user):
        return user_companies(user).filter(id=company.id).exists()
    assigned = get_user_assigned_company(user)
    return bool(assigned and assigned.id == company.id)


def _user_can_acquire_ai(user, company):
    from .draft_notifications import users_with_acquisisci_access
    return user in users_with_acquisisci_access(company)


@require_auth
def api_push_vapid_public_key(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not _user_can_receive_push(request.user, company):
        return JsonResponse({'status': 'error', 'error': 'Permesso negato'}, status=403)
    try:
        from .draft_notifications import get_vapid_public_key
        return JsonResponse({'status': 'success', 'data': {'public_key': get_vapid_public_key()}})
    except Exception as exc:
        return JsonResponse({'status': 'error', 'error': f'Push non disponibile: {exc}'}, status=500)


@require_auth
def api_push_subscribe(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not _user_can_receive_push(request.user, company):
        return JsonResponse({'status': 'error', 'error': 'Permesso negato'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    endpoint = (data.get('endpoint') or '').strip()
    keys = data.get('keys') or {}
    p256dh = (keys.get('p256dh') or '').strip()
    auth = (keys.get('auth') or '').strip()
    if not endpoint or not p256dh or not auth:
        return JsonResponse({'status': 'error', 'error': 'Sottoscrizione push non valida'}, status=400)
    PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={
            'company': company,
            'p256dh': p256dh,
            'auth': auth,
            'user_agent': (request.META.get('HTTP_USER_AGENT') or '')[:255],
        },
    )
    return JsonResponse({'status': 'success'})


@require_auth
def api_push_unsubscribe(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'error': 'JSON non valido'}, status=400)
    endpoint = (data.get('endpoint') or '').strip()
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).delete()
    else:
        PushSubscription.objects.filter(user=request.user).delete()
    return JsonResponse({'status': 'success'})


@require_auth
def api_push_status(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not _user_can_receive_push(request.user, company):
        return JsonResponse({'status': 'error', 'error': 'Permesso negato'}, status=403)
    vapid_configured = False
    vapid_error = ''
    vapid_public_key = ''
    try:
        from .draft_notifications import get_vapid_public_key
        vapid_public_key = get_vapid_public_key()
        vapid_configured = True
    except Exception as exc:
        vapid_error = str(exc)
    current_endpoint = (request.GET.get('endpoint') or '').strip()
    from .draft_notifications import device_label, push_subscriptions_for_company
    subs_qs = push_subscriptions_for_company(company)
    company_devices = subs_qs.count()
    user_devices = subs_qs.filter(user=request.user).count()
    devices = [
        {
            'username': sub.user.get_username(),
            'device': device_label(sub.user_agent),
            'updated_at': sub.updated_at.isoformat(),
            'is_current': bool(current_endpoint and sub.endpoint == current_endpoint),
        }
        for sub in subs_qs.order_by('-updated_at')
    ]
    return JsonResponse({
        'status': 'success',
        'data': {
            'company_devices': company_devices,
            'user_devices': user_devices,
            'devices': devices,
            'vapid_configured': vapid_configured,
            'vapid_error': vapid_error,
            'vapid_public_key': vapid_public_key,
        },
    })


@require_auth
def api_push_test(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not _user_can_receive_push(request.user, company):
        return JsonResponse({'status': 'error', 'error': 'Permesso negato'}, status=403)
    from .draft_notifications import push_subscriptions_for_company, send_test_push
    company_devices = push_subscriptions_for_company(company).count()
    if company_devices == 0:
        return JsonResponse({
            'status': 'error',
            'error': 'Nessun dispositivo registrato. Registra almeno uno smartphone.',
        }, status=400)
    try:
        push_sent, push_failed, push_removed, push_errors = send_test_push(company)
    except Exception as exc:
        return JsonResponse({'status': 'error', 'error': f'Invio test fallito: {exc}'}, status=500)
    return JsonResponse({
        'status': 'success',
        'data': {
            'push_sent': push_sent,
            'push_failed': push_failed,
            'push_removed': push_removed,
            'company_devices': company_devices,
            'push_errors': push_errors[:3],
        },
    })


@require_auth
def api_acquisition_drafts_mark_seen(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    if not _user_can_acquire_ai(request.user, company):
        return JsonResponse({'status': 'error', 'error': 'Permesso negato'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        data = {}
    draft_ids = data.get('draft_ids')
    qs = AcquisitionDraft.objects.filter(company=company, status='pending', source='telegram', viewed_at__isnull=True)
    if draft_ids:
        qs = qs.filter(id__in=[int(i) for i in draft_ids if str(i).isdigit()])
    updated = qs.update(viewed_at=timezone.now())
    return JsonResponse({'status': 'success', 'data': {'marked': updated}})


@require_auth
def api_acquisition_drafts_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    drafts = AcquisitionDraft.objects.filter(company=company, status='pending', source='telegram').prefetch_related('images')[:20]
    return JsonResponse({
        'status': 'success',
        'data': [{
            'id': d.id,
            'source': d.source,
            'operator': d.operator,
            'totale_scassettato': float(d.totale_scassettato),
            'pag_pos_reale': float(d.pag_pos_reale or 0),
            'photo_count': d.images.count(),
            'created_at': d.created_at.isoformat(),
            'viewed': d.viewed_at is not None,
        } for d in drafts],
    })


def _draft_extract_images(draft):
    return [{
        'id': image.id,
        'url': f'/api/acquisition-draft-images/{image.id}/view/',
    } for image in draft.images.all()]


def _draft_extract_json_response(draft, payload, provider, *, cached=False):
    return JsonResponse({
        'status': 'success',
        'provider': provider,
        'cached': cached,
        'data': {
            **payload,
            'images': _draft_extract_images(draft),
        },
    })


@require_auth
def api_acquisition_draft_extract(request, draft_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        company, err = bind_company(request)
        if err:
            return err
        draft = AcquisitionDraft.objects.prefetch_related('images').get(id=draft_id, company=company, status='pending')
    except AcquisitionDraft.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Bozza non trovata'}, status=404)

    if draft.viewed_at is None:
        draft.viewed_at = timezone.now()
        draft.save(update_fields=['viewed_at'])

    force = False
    if request.body:
        try:
            body = json.loads(request.body.decode('utf-8'))
            force = bool(body.get('force'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass

    if draft.extracted_payload and not force:
        provider = draft.extracted_provider or _resolve_ai_provider(request.user, company)
        old_totale = (draft.extracted_payload.get('summary') or {}).get('totale')
        payload = _refresh_draft_extract_payload(draft, draft.extracted_payload)
        if (payload.get('summary') or {}).get('totale') != old_totale:
            draft.extracted_payload = payload
            draft.save(update_fields=['extracted_payload'])
        return _draft_extract_json_response(draft, payload, provider, cached=True)

    try:
        images = []
        for draft_image in draft.images.order_by('id'):
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

        provider = _resolve_ai_provider(request.user, company)
        if provider == 'gemini' and not _get_gemini_key():
            return JsonResponse({'status': 'error', 'error': 'Chiave API Gemini non configurata.'}, status=400)
        if provider == 'groq' and not _get_groq_key():
            return JsonResponse({'status': 'error', 'error': 'Chiave API Groq non configurata.'}, status=400)

        parsed, operator, report_overlays, has_reports = _extract_closure_with_reports(images, company, provider)

        pag_pos_override = None
        if draft.pag_pos_reale and float(draft.pag_pos_reale) > 0:
            pag_pos_override = float(draft.pag_pos_reale)

        payload = _parse_ai_closure_payload(
            parsed,
            company,
            totale_scassettato=draft.totale_scassettato,
            draft_id=draft.id,
            operator=operator,
            report_overlays=report_overlays,
            with_reports=has_reports,
            pag_pos_override=pag_pos_override,
        )
        if report_overlays:
            payload['report_overlays_applied'] = list(report_overlays.keys())

        draft.extracted_payload = payload
        draft.extracted_provider = provider
        draft.extracted_at = timezone.now()
        draft.save(update_fields=['extracted_payload', 'extracted_provider', 'extracted_at'])

        return _draft_extract_json_response(draft, payload, provider, cached=False)
    except Exception as e:
        provider = _resolve_ai_provider(request.user, company)
        if _is_rate_limit_error(e):
            return JsonResponse({'status': 'error', 'error': _rate_limit_message(provider)}, status=429)
        return JsonResponse({'status': 'error', 'error': f'Errore estrazione bozza: {e}'}, status=500)


@require_auth
def api_acquisition_draft_cancel(request, draft_id):
    if request.method not in ['POST', 'DELETE']:
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    updated = AcquisitionDraft.objects.filter(id=draft_id, company=company, status='pending').update(
        status='cancelled',
        completed_at=timezone.now(),
    )
    if not updated:
        return JsonResponse({'status': 'error', 'error': 'Bozza non trovata o già registrata'}, status=404)
    return JsonResponse({'status': 'success'})


# ── VERSAMENTI ────────────────────────────────────────────────────────────────

def _get_movimenti_cassa_net(company):
    from django.db.models import Sum
    entrate = MovimentoCassa.objects.filter(company=company, tipo=MovimentoCassa.TIPO_ENTRATA).aggregate(s=Sum('importo'))['s'] or 0
    uscite = MovimentoCassa.objects.filter(company=company, tipo=MovimentoCassa.TIPO_USCITA).aggregate(s=Sum('importo'))['s'] or 0
    return _money(entrate) - _money(uscite)


def _get_saldo_cassa_base(company):
    from django.db.models import Sum
    tc   = CashClosure.objects.filter(company=company).aggregate(s=Sum('totale_cassetto'))['s'] or 0
    diff = CashClosure.objects.filter(company=company).aggregate(s=Sum('differenza'))['s'] or 0
    vers = Versamento.objects.filter(company=company).aggregate(s=Sum('importo_versato'))['s'] or 0
    return _money(tc) + _money(diff) - _money(vers) + _get_movimenti_cassa_net(company)


def _get_saldo_cassa(company):
    return _get_saldo_cassa_base(company) + _get_setting_money('saldo_cassa_adjustment', company)


@require_auth
def api_versamenti_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    items = Versamento.objects.filter(company=company)
    return JsonResponse({
        'status': 'success',
        'saldo_cassa': float(_get_saldo_cassa(company)),
        'data': [{
            'id': v.id,
            'date': v.date.isoformat(),
            'operator': v.operator,
            'importo_versato': float(v.importo_versato),
            'accantonamento': float(v.accantonamento),
            'saldo_precedente': float(v.saldo_precedente),
            'note': v.note,
            'ricorda_promemoria': v.ricorda_promemoria,
        } for v in items],
    })


@require_auth
def api_versamenti_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
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
        saldo_prec = _get_saldo_cassa(company)
        ricorda = bool(data.get('ricorda_promemoria'))
        v = Versamento.objects.create(
            company=company,
            date=parsed_date,
            operator=data.get('operator', ''),
            importo_versato=importo,
            accantonamento=accantonamento,
            saldo_precedente=saldo_prec,
            note=data.get('note', '').strip(),
            ricorda_promemoria=ricorda,
        )
        if accantonamento > 0:
            FondoCassaMovimento.objects.create(
                company=company,
                date=parsed_date,
                tipo=FondoCassaMovimento.TIPO_ENTRATA,
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
        company, err = bind_company(request)
        if err:
            return err
        versamento = Versamento.objects.get(id=vers_id, company=company)
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
        company, err = bind_company(request)
        if err:
            return err
        v = Versamento.objects.get(id=vers_id, company=company)
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
        if 'ricorda_promemoria' in data:
            v.ricorda_promemoria = bool(data['ricorda_promemoria'])
        if v.accantonamento > v.importo_versato:
            return JsonResponse({'status': 'error', 'error': 'Accantonamento non valido'})
        fondo_qs = FondoCassaMovimento.objects.filter(versamento=v)
        if v.accantonamento > 0:
            descrizione = f'Accantonamento da versamento del {v.date.strftime("%d/%m/%Y")} ({v.operator})'
            if fondo_qs.exists():
                fondo_qs.update(importo=v.accantonamento, date=v.date, descrizione=descrizione)
            else:
                FondoCassaMovimento.objects.create(
                    company=company,
                    date=v.date,
                    tipo=FondoCassaMovimento.TIPO_ENTRATA,
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


# ── MOVIMENTI CASSA ───────────────────────────────────────────────────────────

def _serialize_movimento_cassa(m):
    return {
        'id': m.id,
        'date': m.date.isoformat(),
        'operator': m.operator,
        'tipo': m.tipo,
        'importo': float(m.importo),
        'saldo_precedente': float(m.saldo_precedente),
        'note': m.note,
        'ricorda_promemoria': m.ricorda_promemoria,
    }


@require_auth
def api_movimenti_cassa_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    items = MovimentoCassa.objects.filter(company=company)
    return JsonResponse({
        'status': 'success',
        'saldo_cassa': float(_get_saldo_cassa(company)),
        'data': [_serialize_movimento_cassa(m) for m in items],
    })


@require_auth
def api_movimenti_cassa_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        data = json.loads(request.body)
        parsed_date = parse_date(data.get('date', ''))
        if not parsed_date:
            return JsonResponse({'status': 'error', 'error': 'Data non valida'})
        tipo = data.get('tipo', '').strip().upper()
        if tipo not in (MovimentoCassa.TIPO_ENTRATA, MovimentoCassa.TIPO_USCITA):
            return JsonResponse({'status': 'error', 'error': 'Tipo movimento non valido'})
        importo = _money(data.get('importo'))
        if importo <= 0:
            return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
        saldo_prec = _get_saldo_cassa(company)
        m = MovimentoCassa.objects.create(
            company=company,
            date=parsed_date,
            operator=data.get('operator', '').strip(),
            tipo=tipo,
            importo=importo,
            saldo_precedente=saldo_prec,
            note=data.get('note', '').strip(),
            ricorda_promemoria=bool(data.get('ricorda_promemoria')),
        )
        return JsonResponse({'status': 'success', 'id': m.id, 'saldo_precedente': float(saldo_prec)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


@require_admin
def api_movimenti_cassa_delete(request, mov_id):
    if request.method != 'DELETE':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        company, err = bind_company(request)
        if err:
            return err
        MovimentoCassa.objects.get(id=mov_id, company=company).delete()
        return JsonResponse({'status': 'success'})
    except MovimentoCassa.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)


@require_admin
def api_movimenti_cassa_update(request, mov_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        company, err = bind_company(request)
        if err:
            return err
        m = MovimentoCassa.objects.get(id=mov_id, company=company)
        if 'date' in data:
            parsed = parse_date(data['date'])
            if not parsed:
                return JsonResponse({'status': 'error', 'error': 'Data non valida'})
            m.date = parsed
        if 'operator' in data:
            m.operator = data['operator'].strip()
        if 'tipo' in data:
            tipo = data['tipo'].strip().upper()
            if tipo not in (MovimentoCassa.TIPO_ENTRATA, MovimentoCassa.TIPO_USCITA):
                return JsonResponse({'status': 'error', 'error': 'Tipo movimento non valido'})
            m.tipo = tipo
        if 'importo' in data:
            importo = _money(data['importo'])
            if importo <= 0:
                return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
            m.importo = importo
        if 'note' in data:
            m.note = data['note'].strip()
        if 'ricorda_promemoria' in data:
            m.ricorda_promemoria = bool(data['ricorda_promemoria'])
        m.save()
        return JsonResponse({'status': 'success'})
    except MovimentoCassa.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


# ── FONDO CASSA ───────────────────────────────────────────────────────────────

def _get_fondo_cassa(company):
    from django.db.models import Sum
    entrate = FondoCassaMovimento.objects.filter(company=company, tipo=FondoCassaMovimento.TIPO_ENTRATA).aggregate(s=Sum('importo'))['s'] or 0
    uscite = FondoCassaMovimento.objects.filter(company=company, tipo=FondoCassaMovimento.TIPO_USCITA).aggregate(s=Sum('importo'))['s'] or 0
    return _money(entrate) - _money(uscite)


def _serialize_fondo_cassa_movimento(m):
    return {
        'id': m.id,
        'date': m.date.isoformat(),
        'tipo': m.tipo,
        'importo': float(m.importo),
        'descrizione': m.descrizione,
        'versamento_id': m.versamento_id,
    }


@require_auth
def api_fondo_cassa_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    movimenti = FondoCassaMovimento.objects.filter(company=company).select_related('versamento')
    return JsonResponse({
        'status': 'success',
        'totale': float(_get_fondo_cassa(company)),
        'data': [_serialize_fondo_cassa_movimento(m) for m in movimenti],
    })


@require_admin
def api_fondo_cassa_create(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    company, err = bind_company(request)
    if err:
        return err
    try:
        data = json.loads(request.body)
        parsed_date = parse_date(data.get('date', ''))
        if not parsed_date:
            return JsonResponse({'status': 'error', 'error': 'Data non valida'})
        tipo = data.get('tipo', '').strip().upper()
        if tipo not in (FondoCassaMovimento.TIPO_ENTRATA, FondoCassaMovimento.TIPO_USCITA):
            return JsonResponse({'status': 'error', 'error': 'Tipo movimento non valido'})
        importo = _money(data.get('importo'))
        if importo <= 0:
            return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
        m = FondoCassaMovimento.objects.create(
            company=company,
            date=parsed_date,
            tipo=tipo,
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
        company, err = bind_company(request)
        if err:
            return err
        FondoCassaMovimento.objects.get(id=mov_id, company=company).delete()
        return JsonResponse({'status': 'success'})
    except FondoCassaMovimento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)


@require_admin
def api_fondo_cassa_update(request, mov_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    try:
        data = json.loads(request.body)
        company, err = bind_company(request)
        if err:
            return err
        m = FondoCassaMovimento.objects.get(id=mov_id, company=company)
        if m.versamento_id:
            return JsonResponse({'status': 'error', 'error': 'Movimento da versamento: modifica dal versamento collegato'}, status=400)
        if 'date' in data:
            parsed = parse_date(data['date'])
            if not parsed:
                return JsonResponse({'status': 'error', 'error': 'Data non valida'})
            m.date = parsed
        if 'tipo' in data:
            tipo = data['tipo'].strip().upper()
            if tipo not in (FondoCassaMovimento.TIPO_ENTRATA, FondoCassaMovimento.TIPO_USCITA):
                return JsonResponse({'status': 'error', 'error': 'Tipo movimento non valido'})
            m.tipo = tipo
        if 'importo' in data:
            importo = _money(data['importo'])
            if importo <= 0:
                return JsonResponse({'status': 'error', 'error': 'Importo deve essere maggiore di zero'})
            m.importo = importo
        if 'descrizione' in data:
            m.descrizione = data['descrizione'].strip()
        m.save()
        return JsonResponse({'status': 'success'})
    except FondoCassaMovimento.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Non trovato'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)
