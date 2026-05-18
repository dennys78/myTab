import os
import re
import json

import django
from asgiref.sync import sync_to_async
from django.core.files.base import ContentFile
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# Configura l'ambiente Django per l'uso standalone del bot.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cash_manager.settings')
django.setup()

from reconciliation.models import AcquisitionDraft, AcquisitionDraftImage, AppSetting


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


def _get_telegram_token():
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if token:
        return token
    try:
        return AppSetting.objects.get(key='telegram_bot_token').value.strip()
    except AppSetting.DoesNotExist:
        return ''


def _get_reset_marker_sync():
    try:
        return AppSetting.objects.get(key='telegram_reset_sessions_at').value
    except AppSetting.DoesNotExist:
        return ''


def _remember_chat_sync(chat_id):
    try:
        setting = AppSetting.objects.get(key='telegram_chat_ids')
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
        AppSetting.objects.create(key='telegram_chat_ids', value=value)


async def _prepare_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id if update.effective_chat else None
    if chat_id is not None:
        await sync_to_async(_remember_chat_sync)(chat_id)

    reset_marker = await sync_to_async(_get_reset_marker_sync)()
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


def _save_draft_sync(operator, chat_id, photos, totale_scassettato):
    draft = AcquisitionDraft.objects.create(
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
    draft_id = await sync_to_async(_save_draft_sync)(
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
        "Apri Acquisisci con IA nell'app: troverai la bozza pronta da controllare e confermare."
    )


def run_bot():
    token = _get_telegram_token()
    if not token:
        raise RuntimeError('Token Telegram non configurato in TELEGRAM_BOT_TOKEN o in Impostazioni.')

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("annulla", cancel))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Telegram bot myTab avviato.")
    app.run_polling()


if __name__ == '__main__':
    run_bot()
