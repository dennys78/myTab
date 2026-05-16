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
    # L'OCR mette etichette e valori su righe separate.
    # La riga dei valori ha esattamente 7 importi di fila (contanti, pag_pos, …, totale).
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
        'DESCRIZIONE', 'NOTE', 'PAG', 'CONTANTI', 'DISTRIB', 'RIEPILOGO',
        'TELEFONO', 'CHIUSURA', 'CASSA',
    }

    for line in ocr_text.split('\n'):
        # Rimuovi il simbolo € e i pipe come separatori di colonna
        clean = line.replace('€', '').replace('|', ' ').strip()
        if not clean:
            continue

        # Rimuovi spazzatura OCR iniziale: simboli, parentesi, lettere isolate
        clean = re.sub(r'^[\[\(\{\|©=\-\s\.\,\!\@\#\$\%\^\&\*\~\`\'\"\{\}]+', '', clean)

        # Rimuovi prefisso data (es. "2026-05-09" o "2026-05-09.")
        clean = re.sub(r'^\d{4}[-/\.]\d{2}[-/\.]\d{2}\.?\s*', '', clean)

        # Cerca: nome_reparto (testo) + 3 importi italiani
        m = re.search(
            r'^([A-Za-zÀÈÉÌÒÙàèéìòù][A-Za-zÀÈÉÌÒÙàèéìòù\s\.\-\/0-9]*?)'
            r'\s{2,}'
            r'(-?[\d\.]+,\d{2})'    # entrate
            r'[\s\€\|]+'
            r'(-?[\d\.]+,\d{2})'    # uscite
            r'[\s\€\|]+'
            r'(-?[\d\.]+,\d{2})',   # saldo
            clean,
            re.IGNORECASE
        )
        if not m:
            continue

        desc = re.sub(r'\s+', ' ', m.group(1)).strip().upper()

        # Scarta singolo carattere OCR spurio iniziale (es. "L" davanti a "ART.")
        desc = re.sub(r'^[A-Z]\s+(?=[A-Z])', '', desc)

        if len(desc) < 3:
            continue
        if any(kw in desc for kw in SKIP):
            continue

        data['items'].append({
            'descrizione': desc,
            'entrate': to_float(m.group(2)),
            'uscite':  to_float(m.group(3)),
            'saldo':   to_float(m.group(4)),
        })

    return data
