import json
import base64
import os
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.db import transaction
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from difflib import get_close_matches
from .models import CashClosure, CashClosureItem, Department, AppSetting
from .ocr_parser import parse_closure_receipt
import pytesseract
from PIL import Image, ImageEnhance


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

@csrf_exempt
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

@csrf_exempt
def api_logout(request):
    auth_logout(request)
    return JsonResponse({'status': 'success'})

def api_me(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'error': 'Non autenticato'}, status=401)
    return JsonResponse({'status': 'success', 'data': _user_info(request.user)})


# ── GESTIONE UTENTI (solo amministratori) ────────────────────────────────────

@csrf_exempt
@require_admin
def api_users_list(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)
    users = User.objects.all().order_by('username')
    return JsonResponse({'status': 'success', 'data': [_user_info(u) for u in users]})

@csrf_exempt
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

@csrf_exempt
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

@csrf_exempt
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


@csrf_exempt
@require_auth
def api_insert_closure(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            date_str = data.get('date')
            operator = data.get('operator', 'Sistema Esterno')
            summary = data.get('summary', {})
            items = data.get('items', [])
            
            if not date_str:
                return JsonResponse({'error': 'Campo "date" obbligatorio (Formato YYYY-MM-DD)'}, status=400)
                
            parsed_date = parse_date(date_str)
            if not parsed_date:
                return JsonResponse({'error': 'Formato data non valido, usa YYYY-MM-DD'}, status=400)

            with transaction.atomic():
                # Inserimento Master
                closure = CashClosure.objects.create(
                    date=parsed_date,
                    operator=operator,
                    contanti=float(summary.get('contanti', 0.0)),
                    pag_pos=float(summary.get('pag_pos', 0.0)),
                    cassa_auto=float(summary.get('cassa_auto', 0.0)),
                    reso_cont=float(summary.get('reso_cont', 0.0)),
                    reso_auto=float(summary.get('reso_auto', 0.0)),
                    distrib=float(summary.get('distrib', 0.0)),
                    totale_generale=float(summary.get('totale', 0.0))
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
                        incomes=float(item.get('entrate', 0.0)),
                        expenses=float(item.get('uscite', 0.0)),
                        balance=float(item.get('saldo', 0.0))
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

@csrf_exempt
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

@csrf_exempt
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
                'summary': {
                    'contanti': float(c.contanti),
                    'pag_pos': float(c.pag_pos),
                    'cassa_auto': float(c.cassa_auto),
                    'reso_cont': float(c.reso_cont),
                    'reso_auto': float(c.reso_auto),
                    'distrib': float(c.distrib),
                    'totale': float(c.totale_generale)
                },
                'items': items
            })
            
        return JsonResponse({'status': 'success', 'data': data})
        
    return JsonResponse({'error': 'Metodo non consentito. Usa GET.'}, status=405)
@csrf_exempt
@require_admin
def api_update_closure(request, closure_id):
    if request.method in ['POST', 'PUT']:
        try:
            closure = CashClosure.objects.get(id=closure_id)
            data = json.loads(request.body)
            
            # Aggiorna solo se presenti nel payload
            if 'contanti' in data: closure.contanti = float(data['contanti'])
            if 'pag_pos' in data: closure.pag_pos = float(data['pag_pos'])
            if 'cassa_auto' in data: closure.cassa_auto = float(data['cassa_auto'])
            if 'reso_cont' in data: closure.reso_cont = float(data['reso_cont'])
            if 'reso_auto' in data: closure.reso_auto = float(data['reso_auto'])
            if 'distrib' in data: closure.distrib = float(data['distrib'])
            if 'totale' in data: closure.totale_generale = float(data['totale'])
            
            closure.save()
            
            # Aggiorna gli items se presenti
            items_data = data.get('items', [])
            for item_data in items_data:
                item_id = item_data.get('id')
                if item_id:
                    try:
                        item = CashClosureItem.objects.get(id=item_id, closure=closure)
                        if 'entrate' in item_data: item.incomes = float(item_data['entrate'])
                        if 'uscite' in item_data: item.expenses = float(item_data['uscite'])
                        if 'saldo' in item_data: item.balance = float(item_data['saldo'])
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

@csrf_exempt
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

@csrf_exempt
@require_admin
def api_list_departments(request):
    if request.method == 'GET':
        data = [{'id': d.id, 'name': d.name} for d in Department.objects.all()]
        return JsonResponse({'status': 'success', 'data': data})
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@csrf_exempt
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


@csrf_exempt
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


@csrf_exempt
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
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if not key:
        try:
            key = AppSetting.objects.get(key='groq_api_key').value.strip()
        except AppSetting.DoesNotExist:
            pass
    return key


@csrf_exempt
@require_admin
def api_get_settings(request):
    if request.method == 'GET':
        return JsonResponse({
            'status': 'success',
            'data': {'groq_key_configured': bool(_get_groq_key())},
        })
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


@csrf_exempt
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
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Metodo non consentito.'}, status=405)


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


@csrf_exempt
@require_auth
def api_extract_closure_ai(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Metodo non consentito. Usa POST.'}, status=405)

    api_key = _get_groq_key()
    if not api_key:
        return JsonResponse({'error': 'Chiave API Groq non configurata. Vai su Impostazioni per inserirla.'}, status=500)

    if not request.FILES:
        return JsonResponse({'error': 'Nessuna immagine fornita.'}, status=400)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url='https://api.groq.com/openai/v1')

        # Costruisce il contenuto con tutte le immagini (OpenAI-compatible format)
        content = []
        for file_key in request.FILES:
            f = request.FILES[file_key]
            mime = f.content_type or 'image/jpeg'
            b64 = base64.standard_b64encode(f.read()).decode('utf-8')
            content.append({
                'type': 'image_url',
                'image_url': {'url': f'data:{mime};base64,{b64}'},
            })
        content.append({'type': 'text', 'text': AI_PROMPT})

        response = client.chat.completions.create(
            model='meta-llama/llama-4-scout-17b-16e-instruct',
            max_tokens=2048,
            messages=[{'role': 'user', 'content': content}],
        )

        raw_json = response.choices[0].message.content.strip()
        if raw_json.startswith('```'):
            raw_json = raw_json.split('```')[1]
            if raw_json.startswith('json'):
                raw_json = raw_json[4:]
        parsed = json.loads(raw_json)

        items = []
        for item in parsed.get('items', []):
            entrate = float(item.get('entrate', 0))
            uscite = float(item.get('uscite', 0))
            items.append({
                'descrizione': str(item.get('descrizione', '')).strip().upper(),
                'entrate': entrate,
                'uscite': uscite,
                'saldo': round(entrate - uscite, 2),
            })

        summary = parsed.get('summary', {})

        # Risolve nomi reparti contro archivio (exact → prefix → fuzzy)
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

        return JsonResponse({
            'status': 'success',
            'data': {
                'date': parsed.get('date', ''),
                'operator': 'IA Groq',
                'summary': {
                    'contanti':   float(summary.get('contanti', 0)),
                    'pag_pos':    float(summary.get('pag_pos', 0)),
                    'cassa_auto': float(summary.get('cassa_auto', 0)),
                    'reso_cont':  float(summary.get('reso_cont', 0)),
                    'reso_auto':  float(summary.get('reso_auto', 0)),
                    'distrib':    float(summary.get('distrib', 0)),
                    'totale':     float(summary.get('totale', 0)),
                },
                'items': items,
            }
        })

    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'Risposta IA non in formato JSON valido: {e}'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Errore acquisizione IA: {e}'}, status=500)
