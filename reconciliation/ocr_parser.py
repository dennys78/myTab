import re
from datetime import datetime


def parse_closure_receipt(ocr_text: str) -> dict:
    data = {
        'date': None,
        'total_in': 0.00,
        'contanti': 0.00,
        'pag_pos': 0.00,
        'cassa_auto': 0.00,
        'reso_cont': 0.00,
        'reso_auto': 0.00,
        'distrib': 0.00,
        'items': []
    }

    AMOUNT_RE = re.compile(r'-?[\d\.]+,\d{2}')

    def to_float(s):
        return float(s.strip().replace('.', '').replace(',', '.'))

    # --- DATA ---
    date_match = re.search(r'(?:Data|del)\s+(\d{2}[/-]\d{2}[/-]\d{4})', ocr_text, re.IGNORECASE)
    if date_match:
        try:
            data['date'] = datetime.strptime(date_match.group(1).replace('-', '/'), "%d/%m/%Y").date()
        except ValueError:
            pass

    # --- SUMMARY ---
    # I valori (contanti, pag_pos, …, totale) sono su una riga con 6-7 importi consecutivi.
    # Le etichette ("Contanti", "Pag.Pos"…) sono sulla riga precedente — separata.
    for line in ocr_text.split('\n'):
        amounts = AMOUNT_RE.findall(line.replace('€', ''))
        if len(amounts) >= 6:
            fields = ['contanti', 'pag_pos', 'cassa_auto', 'reso_cont', 'reso_auto', 'distrib', 'total_in']
            for i, field in enumerate(fields):
                if i < len(amounts):
                    data[field] = to_float(amounts[i])
            break

    # --- ITEMS ---
    SKIP = {
        'TOTALE', 'SALDO', 'DATA', 'ENTRATE', 'USCITE', 'REPARTO',
        'DESCRIZIONE', 'NOTE', 'PAG', 'CONTANTI', 'DISTRIB',
        'RIEPILOGO', 'TELEFONO', 'CHIUSURA', 'CASSA',
    }

    for line in ocr_text.split('\n'):
        # Normalizza: rimuovi € e tratta | come spazio
        clean = line.replace('€', '').replace('|', ' ').strip()
        if not clean:
            continue

        # Se la riga contiene una data YYYY-MM-DD, prendi solo la parte dopo
        date_parts = re.split(r'\d{4}[-/\.]\d{2}[-/\.]\d{2}\.?', clean)
        remainder = date_parts[-1] if len(date_parts) > 1 else clean

        # Elimina tutto ciò che precede la prima lettera (simboli OCR, pipe, spazi)
        remainder = re.sub(r'^[^A-Za-zÀÈÉÌÒÙàèéìòù]+', '', remainder)
        if not remainder:
            continue

        # Step 1: estrai il nome (lettere, spazi, punti, trattini)
        name_m = re.match(
            r'^([A-Za-zÀÈÉÌÒÙàèéìòù][A-Za-zÀÈÉÌÒÙàèéìòù\s\.\-\/]*)',
            remainder
        )
        if not name_m:
            continue

        desc = re.sub(r'\s+', ' ', name_m.group(1)).strip().upper()
        if len(desc) < 5:           # filtra rumore OCR breve (es. "EUZU")
            continue
        if any(kw in desc for kw in SKIP):
            continue

        # Step 2: trova tutti gli importi italiani sulla riga (entrate, uscite, saldo)
        amounts = AMOUNT_RE.findall(remainder)
        if len(amounts) < 2:
            continue

        entrate = to_float(amounts[0])
        uscite  = to_float(amounts[1])
        saldo   = to_float(amounts[2]) if len(amounts) >= 3 else round(entrate - uscite, 2)

        data['items'].append({
            'descrizione': desc,
            'entrate': entrate,
            'uscite':  uscite,
            'saldo':   saldo,
        })

    return data
