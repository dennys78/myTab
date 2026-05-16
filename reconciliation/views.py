import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_date
from django.db import transaction
from .models import CashClosure, CashClosureItem
from .ocr_parser import parse_closure_receipt
import pytesseract
from PIL import Image, ImageEnhance


def _preprocess(img):
    img = img.convert('L')
    img = ImageEnhance.Contrast(img).enhance(2.0)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


@csrf_exempt
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
                
                # Inserimento Items (Righe/Reparti)
                for item in items:
                    CashClosureItem.objects.create(
                        closure=closure,
                        department_name=item.get('descrizione', 'Reparto Sconosciuto'),
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
