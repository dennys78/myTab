import os
import re
import json
import asyncio
import time
from datetime import date
from decimal import Decimal

import django
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from django.utils import timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Configura l'ambiente Django per l'uso standalone del bot.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cash_manager.settings')
django.setup()

from reconciliation.models import (
    AcquisitionDraft,
    AcquisitionDraftImage,
    AppSetting,
    Company,
    Versamento,
)
from reconciliation.draft_notifications import notify_new_acquisition_draft, send_unviewed_draft_reminders
from reconciliation.telegram_movimenti import (
    parse_movimento_entrata_message,
    save_movimento_from_telegram,
    message_local_date,
)
from reconciliation.views import _get_saldo_cassa, _money

STEP_AWAITING_POS = 'awaiting_pos'
STEP_AWAITING_SCASSETTO = 'awaiting_scassettato'
STEP_VERSAMENTO_DATE = 'awaiting_versamento_date'

VERSAMENTO_TRIGGER_RE = re.compile(
    r'(?i)^versat[oi]\s*([\d.,\s€]+)$',
)

SALDO_QUERY_RE = re.compile(r'(?i)^saldo(?:\s+cassa)?\s*$')

DATE_TODAY_ALIASES = {
    '',
    'si',
    'sì',
    's',
    'ok',
    'oggi',
    'odierna',
    'yes',
    'y',
    'data odierna',
    'con data odierna',
    'usa oggi',
}


def _initial_session():
    return {
        'photos': [],
        'step': STEP_AWAITING_POS,
        'pag_pos_reale': None,
    }


def _reset(context):
    context.user_data['draft_session'] = _initial_session()
    context.user_data.pop('versamento_session', None)


def _versamento_session(context):
    return context.user_data.get('versamento_session')


def _start_versamento_session(context, importo):
    context.user_data['versamento_session'] = {
        'step': STEP_VERSAMENTO_DATE,
        'importo_versato': importo,
    }


def _parse_versamento_date(text):
    normalized = (text or '').strip().lower()
    if normalized in DATE_TODAY_ALIASES:
        return timezone.localdate()

    match = re.fullmatch(r'(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{2,4}))?', normalized)
    if not match:
        raise ValueError('Data non valida')

    day = int(match.group(1))
    month = int(match.group(2))
    year_raw = match.group(3)
    if year_raw:
        year = int(year_raw)
        if year < 100:
            year += 2000
    else:
        year = timezone.localdate().year

    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError('Data non valida') from exc


def _match_versamento_trigger(text):
    match = VERSAMENTO_TRIGGER_RE.match((text or '').strip())
    if not match:
        return None
    return _parse_amount(match.group(1))


def _parse_amount(text):
    cleaned = text.strip().replace('€', '').replace(' ', '')
    if not re.fullmatch(r'\d{1,9}([.,]\d{1,2})?', cleaned):
        raise ValueError('Importo non valido')
    if ',' in cleaned:
        return float(cleaned.replace('.', '').replace(',', '.'))
    return float(cleaned)


def _money_text(value):
    return f"€ {value:.2f}".replace('.', ',')


def _company_for_token(token):
    if token:
        setting = AppSetting.objects.filter(
            key='telegram_bot_token',
            value=token,
        ).select_related('company').first()
        if setting:
            return setting.company
    return Company.objects.order_by('id').first()


def _get_telegram_token():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if token:
        return token
    setting = AppSetting.objects.filter(key='telegram_bot_token').exclude(value='').select_related('company').first()
    return setting.value.strip() if setting else ''


def _get_setting_sync(company, key, default=''):
    if not company:
        return default
    try:
        return AppSetting.objects.get(company=company, key=key).value
    except AppSetting.DoesNotExist:
        return default


def _get_reset_marker_sync(company):
    return _get_setting_sync(company, 'telegram_reset_sessions_at', '')


def _get_restart_marker_sync(company):
    return _get_setting_sync(company, 'telegram_bot_restart_requested_at', '')


def _remember_chat_sync(company, chat_id):
    if not company:
        return
    try:
        setting = AppSetting.objects.get(company=company, key='telegram_chat_ids')
        chat_ids = set(json.loads(setting.value))
    except (AppSetting.DoesNotExist, json.JSONDecodeError, TypeError):
        chat_ids = set()
        setting = None

    chat_ids.add(str(chat_id))
    value = json.dumps(sorted(chat_ids))
    if setting:
        setting.value = value
        setting.save(update_fields=['value'])
    else:
        AppSetting.objects.create(company=company, key='telegram_chat_ids', value=value)


async def _prepare_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    company = context.application.bot_data.get('company')
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is not None and company:
        await sync_to_async(_remember_chat_sync)(company, chat_id)

    reset_marker = await sync_to_async(_get_reset_marker_sync)(company)
    seen_marker = context.user_data.get('telegram_reset_seen')
    current_session = context.user_data.get('draft_session')
    has_open_session = bool(current_session and current_session.get('photos'))
    if reset_marker and reset_marker != seen_marker:
        if seen_marker is None and not has_open_session:
            context.user_data['telegram_reset_seen'] = reset_marker
            context.user_data.setdefault('draft_session', _initial_session())
            return False
        context.user_data.clear()
        context.user_data['telegram_reset_seen'] = reset_marker
        context.user_data['draft_session'] = _initial_session()
        return True
    context.user_data.setdefault('draft_session', _initial_session())
    return False


def _save_draft_sync(company, operator, chat_id, photos, pag_pos_reale, totale_scassettato):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')
    draft = AcquisitionDraft.objects.create(
        company=company,
        source='telegram',
        operator=operator,
        telegram_chat_id=str(chat_id),
        pag_pos_reale=Decimal(str(pag_pos_reale)).quantize(Decimal('0.01')),
        totale_scassettato=Decimal(str(totale_scassettato)).quantize(Decimal('0.01')),
    )
    for index, photo_bytes in enumerate(photos, start=1):
        AcquisitionDraftImage.objects.create(
            draft=draft,
            image=ContentFile(photo_bytes, name=f'telegram_{chat_id}_{draft.id}_{index}.jpg'),
        )
    notify_new_acquisition_draft(draft, exclude_telegram_chat_id=str(chat_id))
    return draft.id


def _saldo_cassa_sync(company):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')
    return float(_get_saldo_cassa(company))


def _save_versamento_sync(company, operator, importo, versamento_date, note=''):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')
    importo_dec = Decimal(str(importo)).quantize(Decimal('0.01'))
    if importo_dec <= 0:
        raise ValueError('Importo deve essere maggiore di zero')

    saldo_prec = _get_saldo_cassa(company)
    versamento = Versamento.objects.create(
        company=company,
        date=versamento_date,
        operator=(operator or 'Telegram')[:100],
        importo_versato=importo_dec,
        accantonamento=Decimal('0.00'),
        saldo_precedente=saldo_prec,
        note=(note or '').strip(),
        ricorda_promemoria=False,
    )
    saldo_attuale = float(_get_saldo_cassa(company))
    return versamento, float(saldo_prec), saldo_attuale


async def _try_register_movimento_entrata(update, context, text):
    try:
        parsed = parse_movimento_entrata_message(text)
    except ValueError as exc:
        await update.message.reply_text(str(exc))
        return True

    if not parsed:
        return False

    user = update.message.from_user
    operator = user.username or user.first_name or 'Telegram'
    company = context.application.bot_data.get('company')
    movimento_date = await sync_to_async(message_local_date)(update)

    try:
        movimento, _, saldo_dopo = await sync_to_async(save_movimento_from_telegram)(
            company,
            operator,
            parsed,
            movimento_date,
        )
    except Exception as exc:
        await update.message.reply_text(f"Movimento non registrato: {exc}")
        return True

    segno = '+' if movimento.tipo == 'ENTRATA' else '-'
    await update.message.reply_text(
        "Movimento registrato in myTab.\n\n"
        f"Tipo: {movimento.get_tipo_display()}\n"
        f"Descrizione: {movimento.note}\n"
        f"Importo: {segno}{_money_text(float(movimento.importo))}\n"
        f"Data: {movimento.date.strftime('%d/%m/%Y')}\n"
        f"Operatore: {movimento.operator}\n\n"
        "Contanti aggiornati."
    )
    await update.message.reply_text(f"Saldo cassa attuale: {_money_text(saldo_dopo)}")
    return True


async def _watch_restart_requests(app):
    company = app.bot_data.get('company')
    initial_token = app.bot_data.get('telegram_token')
    initial_restart_marker = app.bot_data.get('restart_marker', '')

    while True:
        await asyncio.sleep(10)
        token = await sync_to_async(_get_telegram_token)()
        restart_marker = await sync_to_async(_get_restart_marker_sync)(company)
        if (token and token != initial_token) or (restart_marker and restart_marker != initial_restart_marker):
            print("Riavvio bot Telegram richiesto.")
            os._exit(0)


async def _watch_pending_draft_reminders(app):
    company = app.bot_data.get('company')
    while True:
        await asyncio.sleep(900)
        if company:
            await sync_to_async(send_unviewed_draft_reminders)(company)


async def _post_init(app):
    app.create_task(_watch_restart_requests(app))
    app.create_task(_watch_pending_draft_reminders(app))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    _reset(context)
    await update.message.reply_text(
        "Bot myTab pronto.\n\n"
        "Chiusura cassa: invia una o più foto, poi totale POS e importo scassettato.\n\n"
        "Versamento: scrivi ad esempio\n"
        "Versati 2343,20\n"
        "e segui le istruzioni per la data.\n\n"
        "Movimento entrata: scrivi ad esempio\n"
        "Distributore 505\n"
        "(descrizione + importo, data del messaggio).\n\n"
        "Saldo cassa: comando /saldo oppure scrivi «saldo cassa»."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    _reset(context)
    await update.message.reply_text(
        "Operazione annullata. Invia una nuova foto per la chiusura cassa "
        "oppure scrivi «Versati 1234,50» per un versamento."
    )


async def saldo_cassa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    company = context.application.bot_data.get('company')
    try:
        saldo = await sync_to_async(_saldo_cassa_sync)(company)
    except Exception as exc:
        await update.message.reply_text(f"Impossibile leggere il saldo cassa: {exc}")
        return
    await update.message.reply_text(f"Saldo cassa attuale: {_money_text(saldo)}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    if _versamento_session(context):
        await update.message.reply_text(
            "Stai registrando un versamento.\n\n"
            "Rispondi con la data (gg/mm) oppure «sì» per la data odierna, "
            "oppure usa /annulla."
        )
        return

    session = context.user_data.setdefault('draft_session', _initial_session())

    if session.get('step') == STEP_AWAITING_SCASSETTO:
        await update.message.reply_text(
            "Hai già inserito il totale POS.\n\n"
            "Inserisci l'importo scassettato oppure usa /annulla per ricominciare."
        )
        return

    photo_file = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())
    session['photos'].append(image_bytes)
    session['step'] = STEP_AWAITING_POS

    await update.message.reply_text("Inserisci totale POS reale")


async def _ask_versamento_date(update, importo):
    await update.message.reply_text(
        f"Importo versamento: {_money_text(importo)}\n\n"
        "Vuoi che versi con data odierna?\n"
        "Oppure indica semplicemente la data preferita in formato gg/mm"
        " (es. 31/05 o 31/05/2026)."
    )


async def _complete_versamento(update, context, versamento_date):
    session = _versamento_session(context)
    if not session or session.get('step') != STEP_VERSAMENTO_DATE:
        return False

    importo = session.get('importo_versato')
    if importo is None:
        context.user_data.pop('versamento_session', None)
        await update.message.reply_text("Sessione versamento non valida. Riprova con «Versati 1234,50».")
        return True

    user = update.message.from_user
    operator = user.username or user.first_name or 'Telegram'
    company = context.application.bot_data.get('company')

    try:
        versamento, _, saldo_dopo = await sync_to_async(_save_versamento_sync)(
            company,
            operator,
            importo,
            versamento_date,
            note='Registrato da Telegram',
        )
    except ValueError as exc:
        await update.message.reply_text(f"Versamento non registrato: {exc}")
        context.user_data.pop('versamento_session', None)
        return True
    except Exception as exc:
        await update.message.reply_text(f"Versamento non registrato: {exc}")
        context.user_data.pop('versamento_session', None)
        return True

    context.user_data.pop('versamento_session', None)
    await update.message.reply_text(
        "Versamento registrato in myTab.\n\n"
        f"Importo: {_money_text(float(versamento.importo_versato))}\n"
        f"Data: {versamento.date.strftime('%d/%m/%Y')}\n"
        f"Operatore: {versamento.operator}\n\n"
        "Lo trovi subito nella webapp, sezione Versamenti."
    )
    await update.message.reply_text(
        f"Saldo cassa attuale: {_money_text(saldo_dopo)}"
    )
    return True


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_applied = await _prepare_context(update, context)
    if reset_applied:
        await update.message.reply_text(
            "Sessione Telegram precedente azzerata da myTab.\n\n"
            "Invia una nuova foto della chiusura cassa oppure scrivi «Versati 1234,50»."
        )
        return

    text = (update.message.text or '').strip()

    if SALDO_QUERY_RE.match(text):
        company = context.application.bot_data.get('company')
        try:
            saldo = await sync_to_async(_saldo_cassa_sync)(company)
        except Exception as exc:
            await update.message.reply_text(f"Impossibile leggere il saldo cassa: {exc}")
            return
        await update.message.reply_text(f"Saldo cassa attuale: {_money_text(saldo)}")
        return

    if _versamento_session(context):
        try:
            versamento_date = _parse_versamento_date(text)
        except ValueError:
            await update.message.reply_text(
                "Data non valida.\n\n"
                "Rispondi «sì» per usare la data odierna oppure scrivi la data in formato gg/mm."
            )
            return
        await _complete_versamento(update, context, versamento_date)
        return

    if await _try_register_movimento_entrata(update, context, text):
        return

    try:
        versamento_importo = _match_versamento_trigger(text)
    except ValueError:
        await update.message.reply_text("Importo non valido. Esempio: Versati 2343,20")
        return

    if versamento_importo is not None:
        _start_versamento_session(context, versamento_importo)
        await _ask_versamento_date(update, versamento_importo)
        return

    session = context.user_data.setdefault('draft_session', _initial_session())
    if not session.get('photos'):
        await update.message.reply_text("Prima invia almeno una foto della chiusura cassa.")
        return

    try:
        amount = _parse_amount(update.message.text)
    except ValueError:
        await update.message.reply_text("Importo non valido. Scrivilo così: 1240,00")
        return

    if session.get('step') == STEP_AWAITING_POS:
        session['pag_pos_reale'] = amount
        session['step'] = STEP_AWAITING_SCASSETTO
        await update.message.reply_text("Inserisci l'importo scassettato")
        return

    if session.get('step') != STEP_AWAITING_SCASSETTO:
        await update.message.reply_text("Inserisci totale POS reale")
        return

    totale_scassettato = amount
    pag_pos_reale = session.get('pag_pos_reale')
    if pag_pos_reale is None:
        await update.message.reply_text("Inserisci totale POS reale")
        session['step'] = STEP_AWAITING_POS
        return

    user = update.message.from_user
    operator = user.username or user.first_name or 'Telegram'
    company = context.application.bot_data.get('company')
    await sync_to_async(_save_draft_sync)(
        company,
        operator,
        update.message.chat_id,
        session['photos'],
        pag_pos_reale,
        totale_scassettato,
    )
    photo_count = len(session['photos'])
    _reset(context)

    await update.message.reply_text(
        "Foglio cassa registrato in myTab.\n\n"
        f"Foto: {photo_count}\n"
        f"POS reale: {_money_text(pag_pos_reale)}\n"
        f"Totale scassettato: {_money_text(totale_scassettato)}\n\n"
        "Gli utenti myTab riceveranno una notifica push e un messaggio Telegram (se configurato)."
    )


def run_bot():
    while True:
        token = _get_telegram_token()
        if not token:
            print("Token Telegram non configurato. Nuovo controllo tra 30 secondi.")
            time.sleep(30)
            continue

        company = _company_for_token(token)
        if not company:
            print("Nessuna azienda disponibile per il bot Telegram. Nuovo controllo tra 30 secondi.")
            time.sleep(30)
            continue

        app = ApplicationBuilder().token(token).post_init(_post_init).build()
        app.bot_data['telegram_token'] = token
        app.bot_data['company'] = company
        app.bot_data['restart_marker'] = _get_restart_marker_sync(company)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("annulla", cancel))
        app.add_handler(CommandHandler("saldo", saldo_cassa))
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print(f"Telegram bot myTab avviato per azienda: {company.denominazione}.")
        app.run_polling()


if __name__ == '__main__':
    run_bot()
