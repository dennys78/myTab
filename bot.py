import os
import re
import json
import asyncio
import time

import django
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Configura l'ambiente Django per l'uso standalone del bot.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cash_manager.settings')
django.setup()

from reconciliation.models import AcquisitionDraft, AcquisitionDraftImage, AppSetting, Company


def _initial_session():
    return {
        'photos': [],
        'awaiting_amount': False,
    }


def _reset(context):
    context.user_data['draft_session'] = _initial_session()


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


def _save_draft_sync(company, operator, chat_id, photos, totale_scassettato):
    if not company:
        raise RuntimeError('Nessuna azienda configurata per il bot Telegram.')
    draft = AcquisitionDraft.objects.create(
        company=company,
        source='telegram',
        operator=operator,
        telegram_chat_id=str(chat_id),
        totale_scassettato=totale_scassettato,
    )
    for index, photo_bytes in enumerate(photos, start=1):
        AcquisitionDraftImage.objects.create(
            draft=draft,
            image=ContentFile(photo_bytes, name=f'telegram_{chat_id}_{draft.id}_{index}.jpg'),
        )
    return draft.id


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


async def _post_init(app):
    app.create_task(_watch_restart_requests(app))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    _reset(context)
    await update.message.reply_text(
        "Bot myTab pronto.\n\n"
        "Invia una o più foto della chiusura cassa. Quando hai finito, scrivi l'importo scassettato, ad esempio 1240,00."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    _reset(context)
    await update.message.reply_text("Bozza annullata. Invia una nuova foto per ricominciare.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _prepare_context(update, context)
    session = context.user_data.setdefault('draft_session', _initial_session())
    photo_file = await update.message.photo[-1].get_file()
    image_bytes = bytes(await photo_file.download_as_bytearray())
    session['photos'].append(image_bytes)
    session['awaiting_amount'] = True

    count = len(session['photos'])
    await update.message.reply_text(
        f"Foto {count} ricevuta.\n\n"
        "Invia un'altra foto oppure scrivi l'importo scassettato per creare la bozza in myTab."
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_applied = await _prepare_context(update, context)
    if reset_applied:
        await update.message.reply_text(
            "Sessione Telegram precedente azzerata da myTab.\n\n"
            "Invia una nuova foto della chiusura cassa per ricominciare."
        )
        return

    session = context.user_data.setdefault('draft_session', _initial_session())
    if not session.get('photos'):
        await update.message.reply_text("Prima invia almeno una foto della chiusura cassa.")
        return

    try:
        totale_scassettato = _parse_amount(update.message.text)
    except ValueError:
        await update.message.reply_text("Importo non valido. Scrivilo così: 1240,00")
        return

    user = update.message.from_user
    operator = user.username or user.first_name or 'Telegram'
    company = context.application.bot_data.get('company')
    draft_id = await sync_to_async(_save_draft_sync)(
        company,
        operator,
        update.message.chat_id,
        session['photos'],
        totale_scassettato,
    )
    photo_count = len(session['photos'])
    _reset(context)

    await update.message.reply_text(
        "Bozza acquisizione creata in myTab.\n\n"
        f"Foto ricevute: {photo_count}\n"
        f"Totale scassettato: {_money_text(totale_scassettato)}\n\n"
        "Gli utenti collegati all'app riceveranno una notifica.\n"
        "Apri Acquisisci con IA: troverai la bozza pronta da controllare e confermare."
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
        app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

        print(f"Telegram bot myTab avviato per azienda: {company.denominazione}.")
        app.run_polling()


if __name__ == '__main__':
    run_bot()
