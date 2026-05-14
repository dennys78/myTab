import os
import io
import django
import pytesseract
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from asgiref.sync import sync_to_async
from django.utils import timezone

# Configura l'ambiente Django per l'uso standalone del bot
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cash_manager.settings')
django.setup()

from reconciliation.models import CashClosure
from reconciliation.ocr_parser import parse_closure_receipt

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Benvenuto nel Bot di Ingestion Casse!\n\n"
        "Invia una **foto della schermata di chiusura cassa** e io la registrerò automaticamente a sistema."
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = await update.message.reply_text("⏳ Download dell'immagine in corso...")
    
    try:
        # 1. Scarica la foto alla massima risoluzione disponibile
        photo_file = await update.message.photo[-1].get_file()
        image_bytes = await photo_file.download_as_bytearray()
        image = Image.open(io.BytesIO(image_bytes))
        
        await message.edit_text("🔍 Estrazione del testo tramite OCR...")
        
        # 2. OCR Estrazione
        extracted_text = pytesseract.image_to_string(image, lang='ita')
        
        # 3. Parsing dei dati con le Regex
        parsed_data = parse_closure_receipt(extracted_text)
        
        if parsed_data['total_in'] == 0.0:
            await message.edit_text("⚠️ Attenzione: Non sono riuscito a leggere chiaramente gli importi. Riprova con un'immagine più nitida.")
            return

        # 4. Salvataggio su DB
        closure = await sync_to_async(CashClosure.objects.create)(
            operator=user.username or user.first_name,
            date=parsed_data['date'] or timezone.now().date(),
            total_in=parsed_data['total_in'],
            total_out=parsed_data['total_out'],
            calculated_balance=parsed_data['calculated_balance']
        )
        
        # 5. Feedback di successo formattato
        response = (
            f"✅ **Chiusura Cassa Acquisita!**\n\n"
            f"📅 Data: {parsed_data['date']}\n"
            f"👤 Operatore: {user.username or user.first_name}\n\n"
            f"📈 **Incassi:** € {parsed_data['total_in']:.2f}\n"
            f"📉 **Uscite:** € {parsed_data['total_out']:.2f}\n"
            f"💰 **Saldo Finale:** € {parsed_data['calculated_balance']:.2f}\n\n"
            f"Il dato è ora disponibile nella dashboard per la riconciliazione."
        )
        await message.edit_text(response, parse_mode='Markdown')

    except Exception as e:
        await message.edit_text(f"❌ Si è verificato un errore durante l'elaborazione: {str(e)}")

def run_bot():
    # Sostituisci "IL_TUO_TELEGRAM_TOKEN" con il token reale del tuo bot
    app = ApplicationBuilder().token("8690393245:AAHdGuqzlA0njiQvbSbhnx1jcTqZJc2mzFw").build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    print("🤖 Telegram Ingestion Bot avviato...")
    app.run_polling()

if __name__ == '__main__':
    run_bot()
