import re
from datetime import datetime

def parse_closure_receipt(ocr_text: str) -> dict:
    """
    Analizza il testo grezzo estratto dall'OCR e restituisce un dizionario strutturato.
    Gestisce formati numerici italiani (es. 1.250,00).
    """
    data = {
        'date': None,
        'total_in': 0.00,
        'total_out': 0.00,
        'calculated_balance': 0.00
    }
    
    # Estrazione Data (es: "Data: 14/05/2026" o "14-05-2026")
    date_match = re.search(r'(?:Data|Del)[\s:]*(\d{2}[/-]\d{2}[/-]\d{4})', ocr_text, re.IGNORECASE)
    if date_match:
        # Normalizziamo la data per Django (YYYY-MM-DD)
        raw_date = date_match.group(1).replace('-', '/')
        data['date'] = datetime.strptime(raw_date, "%d/%m/%Y").date()
        
    # Helper function per convertire stringhe "1.250,00" in float 1250.00
    def str_to_float(match_obj):
        if match_obj:
            return float(match_obj.group(1).replace('.', '').replace(',', '.'))
        return 0.00

    # Estrazione Totale Incassi
    in_match = re.search(r'TOTALE INCASS[IO][\s:]*([\d\.]+,\d{2})', ocr_text, re.IGNORECASE)
    data['total_in'] = str_to_float(in_match)
        
    # Estrazione Totale Uscite
    out_match = re.search(r'TOTALE USCITE[\s:]*([\d\.]+,\d{2})', ocr_text, re.IGNORECASE)
    data['total_out'] = str_to_float(out_match)
        
    # Estrazione Saldo Finale
    balance_match = re.search(r'SALDO FINALE[\s:]*([\d\.]+,\d{2})', ocr_text, re.IGNORECASE)
    data['calculated_balance'] = str_to_float(balance_match)
        
    return data
