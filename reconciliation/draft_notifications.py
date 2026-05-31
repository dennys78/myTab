"""Notifiche bozze Telegram: Web Push (browser) + messaggi Telegram."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request

from django.contrib.auth.models import User

from .company_scope import get_user_assigned_company, is_admin_user, user_companies
from .models import AppSetting, Company, PushSubscription
from .nav_permissions import default_sidebar_menu, normalize_sidebar_menu

logger = logging.getLogger(__name__)

VAPID_EMAIL = os.environ.get('WEB_PUSH_VAPID_EMAIL', 'mailto:admin@mytab.local').strip()


def _get_global_setting(key):
    env_map = {
        'web_push_vapid_private': 'WEB_PUSH_VAPID_PRIVATE_KEY',
        'web_push_vapid_public': 'WEB_PUSH_VAPID_PUBLIC_KEY',
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


def ensure_vapid_keys():
    public_key = _get_global_setting('web_push_vapid_public')
    private_key = _get_global_setting('web_push_vapid_private')
    if public_key and private_key:
        return public_key, private_key

    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    from py_vapid import Vapid02, b64urlencode

    vapid = Vapid02()
    vapid.generate_keys()
    private_pem = vapid.private_pem()
    private_key = private_pem.decode('utf-8') if isinstance(private_pem, bytes) else private_pem
    raw_public = vapid.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key = b64urlencode(raw_public)
    _set_global_setting('web_push_vapid_private', private_key)
    _set_global_setting('web_push_vapid_public', public_key)
    return public_key, private_key


def get_vapid_public_key():
    return ensure_vapid_keys()[0]


def _vapid_signer_from_pem(private_key_pem):
    from py_vapid import Vapid02

    pem_bytes = private_key_pem.encode('utf-8') if isinstance(private_key_pem, str) else private_key_pem
    return Vapid02.from_pem(pem_bytes)


def _user_sidebar_menu(user):
    is_admin = is_admin_user(user)
    try:
        menu = user.profile.sidebar_menu
        if not menu:
            return default_sidebar_menu(is_admin)
        return normalize_sidebar_menu(menu, is_admin)
    except Exception:
        return default_sidebar_menu(is_admin)


def users_with_acquisisci_access(company):
    if not company:
        return []
    eligible = []
    for user in User.objects.filter(is_active=True).select_related('profile'):
        if 'acquisisci-ai' not in _user_sidebar_menu(user):
            continue
        if is_admin_user(user):
            if user_companies(user).filter(id=company.id).exists():
                eligible.append(user)
        else:
            assigned = get_user_assigned_company(user)
            if assigned and assigned.id == company.id:
                eligible.append(user)
    return eligible


def users_with_company_push_access(company):
    if not company:
        return []
    eligible = []
    for user in User.objects.filter(is_active=True):
        if is_admin_user(user):
            if user_companies(user).filter(id=company.id).exists():
                eligible.append(user)
        else:
            assigned = get_user_assigned_company(user)
            if assigned and assigned.id == company.id:
                eligible.append(user)
    return eligible


def push_subscriptions_for_company(company, user_ids=None):
    if user_ids is None:
        user_ids = [u.id for u in users_with_company_push_access(company)]
    if not user_ids:
        return PushSubscription.objects.none()
    return PushSubscription.objects.filter(user_id__in=user_ids).select_related('user')


def device_label(user_agent):
    ua = (user_agent or '').lower()
    if 'iphone' in ua or 'ipad' in ua:
        return 'iPhone/iPad'
    if 'android' in ua:
        return 'Android'
    if 'mac os' in ua or 'macintosh' in ua:
        return 'Mac'
    if 'windows' in ua:
        return 'Windows'
    if 'linux' in ua:
        return 'Linux'
    return 'Browser'


def _get_telegram_token(company):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        try:
            token = AppSetting.objects.get(company=company, key='telegram_bot_token').value.strip()
        except AppSetting.DoesNotExist:
            pass
    return token


def _get_telegram_chat_ids(company):
    chat_ids = set()
    try:
        raw = AppSetting.objects.get(company=company, key='telegram_chat_ids').value
        chat_ids.update(str(chat_id) for chat_id in json.loads(raw))
    except (AppSetting.DoesNotExist, json.JSONDecodeError, TypeError):
        pass
    return sorted(chat_id for chat_id in chat_ids if chat_id.strip())


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


def _money_text(value):
    return f"€ {float(value):.2f}".replace('.', ',')


def _draft_telegram_message(draft, *, reminder=False):
    prefix = 'Promemoria myTab' if reminder else 'Nuova chiusura da contabilizzare'
    viewed = ' (non ancora aperta in app)' if reminder else ''
    lines = [
        f"{prefix}{viewed}",
        '',
        f"Operatore: {draft.operator or 'Telegram'}",
        f"Foto: {draft.images.count()}",
    ]
    if float(draft.pag_pos_reale or 0) > 0:
        lines.append(f"POS reale: {_money_text(draft.pag_pos_reale)}")
    lines.append(f"Scassettato: {_money_text(draft.totale_scassettato)}")
    lines.append('')
    lines.append('Apri myTab → Acquisisci con IA per contabilizzare.')
    return '\n'.join(lines)


def _push_payload_for_draft(draft, *, reminder=False):
    title = 'Promemoria chiusura cassa' if reminder else 'Foglio cassa da contabilizzare'
    body_parts = [draft.operator or 'Telegram', f"{draft.images.count()} foto"]
    if float(draft.pag_pos_reale or 0) > 0:
        body_parts.append(f"POS {_money_text(draft.pag_pos_reale)}")
    body_parts.append(f"scassettato {_money_text(draft.totale_scassettato)}")
    return {
        'title': title,
        'body': ' · '.join(body_parts),
        'url': '/?view=acquisisci-ai',
        'tag': f'mytab-draft-{draft.id}',
    }


def send_web_push(subscription, payload):
    try:
        from pywebpush import WebPushException, webpush
    except ImportError as exc:
        logger.error('pywebpush non installato: %s', exc)
        return False, 'pywebpush non installato', False

    _, private_key = ensure_vapid_keys()
    subscription_info = {
        'endpoint': subscription.endpoint,
        'keys': {
            'p256dh': subscription.p256dh,
            'auth': subscription.auth,
        },
    }
    vapid_signer = _vapid_signer_from_pem(private_key)
    last_exc = None
    last_status = None

    for encoding in ('aes128gcm', 'aesgcm'):
        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=vapid_signer,
                vapid_claims={'sub': VAPID_EMAIL},
                content_encoding=encoding,
            )
            return True, None, False
        except WebPushException as exc:
            last_exc = exc
            last_status = getattr(getattr(exc, 'response', None), 'status_code', None)
            if last_status in (401, 403):
                break
        except Exception as exc:
            last_exc = exc
            last_status = None
            break

    removed = False
    if last_status in (401, 403, 404, 410):
        subscription.delete()
        removed = True

    err = str(last_exc).strip() if last_exc else 'Invio push fallito'
    if not err and last_status:
        err = f'HTTP {last_status}'
    logger.warning('Web push failed (%s): %s', last_status, last_exc)
    return False, err, removed


def send_web_push_to_company(company, payload, user_ids=None):
    qs = push_subscriptions_for_company(company, user_ids=user_ids)
    sent = 0
    for subscription in qs:
        ok, _, _ = send_web_push(subscription, payload)
        if ok:
            sent += 1
    return sent


def send_test_push(company):
    payload = {
        'title': 'myTab — test notifica',
        'body': 'Se vedi questo messaggio, le push funzionano correttamente.',
        'url': '/?view=impostazioni',
        'tag': 'mytab-push-test',
    }
    qs = push_subscriptions_for_company(company)
    sent = 0
    failed = 0
    removed = 0
    errors = []
    for subscription in qs:
        ok, err, was_removed = send_web_push(subscription, payload)
        if ok:
            sent += 1
        else:
            failed += 1
            if was_removed:
                removed += 1
            if err and err not in errors:
                errors.append(err)
    return sent, failed, removed, errors


def send_web_push_for_draft(draft, user_ids=None, *, reminder=False):
    payload = _push_payload_for_draft(draft, reminder=reminder)
    if user_ids is None:
        user_ids = [u.id for u in users_with_acquisisci_access(draft.company)]
    qs = push_subscriptions_for_company(draft.company, user_ids=user_ids)

    sent = 0
    for subscription in qs:
        ok, _, _ = send_web_push(subscription, payload)
        if ok:
            sent += 1
    return sent


def send_telegram_for_draft(draft, *, exclude_chat_id=None, reminder=False):
    token = _get_telegram_token(draft.company)
    if not token:
        return 0

    chat_ids = _get_telegram_chat_ids(draft.company)
    exclude = str(exclude_chat_id).strip() if exclude_chat_id else ''
    message = _draft_telegram_message(draft, reminder=reminder)
    sent = 0
    for chat_id in chat_ids:
        if exclude and chat_id == exclude:
            continue
        try:
            if _send_telegram_message(token, chat_id, message):
                sent += 1
        except Exception as exc:
            logger.warning('Telegram notify failed for chat %s: %s', chat_id, exc)
    return sent


def notify_new_acquisition_draft(draft, exclude_telegram_chat_id=None):
    """Invia Web Push + Telegram quando arriva una nuova bozza."""
    push_sent = send_web_push_for_draft(draft)
    telegram_sent = send_telegram_for_draft(
        draft,
        exclude_chat_id=exclude_telegram_chat_id,
        reminder=False,
    )
    return {'push_sent': push_sent, 'telegram_sent': telegram_sent}


def send_unviewed_draft_reminders(company, min_age_minutes=15):
    """Promemoria Telegram + push per bozze pending mai aperte in app."""
    from datetime import timedelta

    from django.utils import timezone

    from .models import AcquisitionDraft

    if not company:
        return {'drafts': 0, 'push_sent': 0, 'telegram_sent': 0}

    threshold = timezone.now() - timedelta(minutes=min_age_minutes)
    drafts = AcquisitionDraft.objects.filter(
        company=company,
        status='pending',
        source='telegram',
        viewed_at__isnull=True,
        telegram_reminder_sent_at__isnull=True,
        created_at__lte=threshold,
    ).prefetch_related('images')

    drafts = list(drafts)

    push_sent = 0
    telegram_sent = 0
    for draft in drafts:
        push_sent += send_web_push_for_draft(draft, reminder=True)
        telegram_sent += send_telegram_for_draft(draft, reminder=True)
        draft.telegram_reminder_sent_at = timezone.now()
        draft.save(update_fields=['telegram_reminder_sent_at'])

    return {'drafts': len(drafts), 'push_sent': push_sent, 'telegram_sent': telegram_sent}


def _normalize_dept(name):
    return ' '.join(str(name or '').upper().split())


def _is_tabacchi(name):
    n = _normalize_dept(name)
    return n == 'TABACCHI' or n.startswith('TABACCH')


def _is_gratta_e_vinci(name):
    n = _normalize_dept(name)
    return 'GRATTA' in n and 'VINCI' in n


def _item_incassato(item):
    try:
        entrate = float(item.get('entrate', item.get('incomes')) or 0)
    except (TypeError, ValueError):
        entrate = 0.0
    try:
        uscite = abs(float(item.get('uscite', item.get('expenses')) or 0))
    except (TypeError, ValueError):
        uscite = 0.0
    if entrate > 0:
        return round(entrate, 2)
    saldo = round(entrate - uscite, 2)
    return saldo if saldo > 0 else 0.0


def build_closure_incasso_summary(items, summary):
    tabacchi = 0.0
    gratta = 0.0
    totale = 0.0
    for item in items or []:
        name = item.get('descrizione') or item.get('department_name') or ''
        inc = _item_incassato(item)
        totale += inc
        if _is_tabacchi(name):
            tabacchi += inc
        if _is_gratta_e_vinci(name):
            gratta += inc
    try:
        differenza = round(float(summary.get('differenza') or 0), 2)
    except (TypeError, ValueError):
        differenza = 0.0
    return {
        'tabacchi': round(tabacchi, 2),
        'gratta': round(gratta, 2),
        'differenza': differenza,
        'totale': round(totale, 2),
    }


def _closure_saved_push_payload(closure, incasso_summary, operator):
    date_str = closure.date.strftime('%d/%m/%Y') if closure.date else ''
    body = '\n'.join([
        f"Incassato tabacchi: {_money_text(incasso_summary['tabacchi'])}",
        f"Incassato gratta e vinci: {_money_text(incasso_summary['gratta'])}",
        f"Differenza: {_money_text(incasso_summary['differenza'])}",
        f"Totale incassato: {_money_text(incasso_summary['totale'])}",
    ])
    op = (operator or closure.operator or '').strip()
    title = f"Chiusura registrata · {date_str}"
    if op:
        title = f"{title} · {op}"
    return {
        'title': title,
        'body': body,
        'url': '/?view=chiusure',
        'tag': f'mytab-closure-{closure.id}',
    }


def _closure_telegram_message(closure, incasso_summary, operator):
    date_str = closure.date.strftime('%d/%m/%Y') if closure.date else ''
    lines = [
        f'Chiusura registrata · {date_str}',
        '',
        f'Operatore: {operator or closure.operator or "—"}',
        f"Incassato tabacchi: {_money_text(incasso_summary['tabacchi'])}",
        f"Incassato gratta e vinci: {_money_text(incasso_summary['gratta'])}",
        f"Differenza: {_money_text(incasso_summary['differenza'])}",
        f"Totale incassato: {_money_text(incasso_summary['totale'])}",
    ]
    return '\n'.join(lines)


def send_telegram_closure_saved(company, closure, incasso_summary, operator=''):
    token = _get_telegram_token(company)
    if not token:
        return 0
    message = _closure_telegram_message(closure, incasso_summary, operator)
    sent = 0
    for chat_id in _get_telegram_chat_ids(company):
        try:
            if _send_telegram_message(token, chat_id, message):
                sent += 1
        except Exception as exc:
            logger.warning('Telegram riepilogo chiusura fallito per chat %s: %s', chat_id, exc)
    return sent


def notify_closure_saved(company, closure, items, summary, operator=''):
    """Push di riepilogo incasso a tutti i dispositivi iscritti + Telegram."""
    if not company or not closure:
        return 0
    incasso = build_closure_incasso_summary(items, summary or {})
    payload = _closure_saved_push_payload(closure, incasso, operator)
    push_sent = send_web_push_to_company(company, payload)
    send_telegram_closure_saved(company, closure, incasso, operator)
    return push_sent
