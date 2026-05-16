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

    def to_float(s):
        if s:
            return float(s.strip().replace('.', '').replace(',', '.'))
        return 0.00

    # Data: "del 09/05/2026" oppure "Data: 14/05/2026"
    date_match = re.search(r'(?:Data|del)[\s:]+(\d{2}[/-]\d{2}[/-]\d{4})', ocr_text, re.IGNORECASE)
    if date_match:
        try:
            raw = date_match.group(1).replace('-', '/')
            data['date'] = datetime.strptime(raw, "%d/%m/%Y").date()
        except ValueError:
            pass

    # Campi riepilogo in fondo (seconda immagine)
    # Es: "Contanti  3.682,80 €"
    patterns = {
        'contanti':   r'[Cc]ontanti\s+([\d\.]+,\d{2})',
        'pag_pos':    r'[Pp]ag\.?\s*[Pp]os\s+([\d\.]+,\d{2})',
        'cassa_auto': r'[Cc]assa\s+[Aa]uto\s+([\d\.]+,\d{2})',
        'reso_cont':  r'[Rr]eso\s+[Cc]ont\.?\s+([\d\.]+,\d{2})',
        'reso_auto':  r'[Rr]eso\s+[Aa]uto\s+([\d\.]+,\d{2})',
        'distrib':    r'[Dd]istrib\.?\s+([\d\.]+,\d{2})',
        'total_in':   r'TOTALE\s+([\d\.]+,\d{2})',
    }
    for field, pattern in patterns.items():
        m = re.search(pattern, ocr_text, re.IGNORECASE)
        if m:
            data[field] = to_float(m.group(1))

    # Righe reparto — formato tabella:
    # "2026-05-09  TABACCHI   3.106,20 €   0,00 €   3.106,20 €   01"
    # La data iniziale è opzionale (OCR potrebbe non stamparla su ogni riga).
    SKIP = {'TOTALE', 'SALDO', 'DATA', 'ENTRATE', 'USCITE', 'REPARTO', 'DESCRIZIONE', 'NOTE', 'PAG'}
    for line in ocr_text.split('\n'):
        clean = line.replace('€', '').strip()
        if not clean:
            continue

        # Pattern: (data opzionale) + nome reparto + 3 importi
        m = re.search(
            r'(?:\d{4}[-/]\d{2}[-/]\d{2}\s+)?'        # data opzionale
            r'([A-ZÀÈÌÒÙA-Z][A-Z\sÀÈÉÌÒÙ\.\-\/]+?)'  # nome reparto (almeno maiuscolo)
            r'\s{2,}'                                   # almeno 2 spazi (separa dal numero)
            r'([\d\.]+,\d{2})'                         # entrate
            r'\s+([\d\.]+,\d{2})'                      # uscite
            r'\s+([\d\.]+,\d{2})',                      # saldo
            clean
        )
        if not m:
            continue

        desc = m.group(1).strip()
        if len(desc) < 3:
            continue
        if any(kw in desc.upper() for kw in SKIP):
            continue

        data['items'].append({
            'descrizione': desc,
            'entrate': to_float(m.group(2)),
            'uscite':  to_float(m.group(3)),
            'saldo':   to_float(m.group(4)),
        })

    return data
