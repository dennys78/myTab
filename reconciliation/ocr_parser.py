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

    # Three amount formats:
    # 1. Italian comma-decimal: 1.234,56
    # 2. OCR dropped comma, uses €: 184140€ → 1841.40
    # 3. OCR read comma as period (period-decimal): 42.20 (1–3 digits before period)
    AMOUNT_RE = re.compile(r'-?[\d\.]+,\d{2}|-?\d{4,}\s*€|-?\d{1,3}\.\d{2}(?!\d)')

    def to_float(s):
        s = s.strip()
        if ',' in s:
            return float(s.replace('€', '').replace('.', '').replace(',', '.'))
        # No-comma format: digits-only + € → insert decimal before last 2 digits
        s = s.replace('€', '').replace(' ', '')
        negative = s.startswith('-')
        digits = s.lstrip('-').replace('.', '')
        val = int(digits) / 100
        return -val if negative else val

    # --- DATA ---
    date_match = re.search(r'(?:Data|del)\s+(\d{2}[/-]\d{2}[/-]\d{4})', ocr_text, re.IGNORECASE)
    if date_match:
        try:
            data['date'] = datetime.strptime(date_match.group(1).replace('-', '/'), "%d/%m/%Y").date()
        except ValueError:
            pass

    # --- SUMMARY ---
    # Summary row has 6-7 Italian-format amounts on one line (label row is separate).
    for line in ocr_text.split('\n'):
        amounts = re.findall(r'-?[\d\.]+,\d{2}', line.replace('€', ''))
        if len(amounts) >= 6:
            fields = ['contanti', 'pag_pos', 'cassa_auto', 'reso_cont', 'reso_auto', 'distrib', 'total_in']
            for i, field in enumerate(fields):
                if i < len(amounts):
                    data[field] = to_float(amounts[i])
            break

    # --- ITEMS ---
    # Kept minimal: only words that appear in lines that also have amounts (subtotal rows).
    # PAG, CASSA, CONTANTI, TELEFONO etc. removed because they appear in header/info lines
    # with no amounts (filtered by the amounts check) OR in legitimate dept names (PAG FORNITORI).
    SKIP = {
        'TOTALE', 'SALDO', 'DATA',
        'DESCRIZIONE', 'REPARTO',
        'RIEPILOGO', 'CHIUSURA',
    }

    for line in ocr_text.split('\n'):
        # orig keeps € for the extended amount pattern; pipe → space for consistency
        orig = line.replace('|', ' ')
        clean = orig.replace('€', '').strip()
        if not clean:
            continue

        # Item rows always have a date (ISO: 2026-05-09 or Italian: 16/04/2026)
        date_parts = re.split(r'\d{4}[-/\.]\d{2}[-/\.]\d{2}\.?|\d{2}[/-]\d{2}[/-]\d{4}', clean)
        has_date = len(date_parts) > 1
        remainder = date_parts[-1] if has_date else clean
        remainder = re.sub(r'^[^A-Za-zÀÈÉÌÒÙàèéìòù]+', '', remainder)
        if not remainder:
            continue

        # Step 1: extract department name from the first alphabetic run
        name_m = re.match(
            r'^([A-Za-zÀÈÉÌÒÙàèéìòù][A-Za-zÀÈÉÌÒÙàèéìòù\s\.\-\/]*)',
            remainder
        )
        desc = re.sub(r'\s+', ' ', name_m.group(1)).strip().upper() if name_m else ''

        # Fallback: if the first token is OCR noise (e.g. "euzu"), find the first word ≥ 5 letters
        if len(desc) < 5:
            alt = re.search(
                r'[A-Za-zÀÈÉÌÒÙàèéìòù]{5,}(?:\s+[A-Za-zÀÈÉÌÒÙàèéìòù\.\/\-]+)*',
                remainder
            )
            desc = re.sub(r'\s+', ' ', alt.group()).strip().upper() if alt else ''
            if len(desc) < 5:
                continue

        if any(kw in desc for kw in SKIP):
            continue

        # Step 2: extract amounts from the original line (with €) so the extended pattern works.
        # This captures both standard "154,80" and garbled "15480€" → 154.80 forms.
        amounts_raw = AMOUNT_RE.findall(orig)
        amounts = [to_float(a) for a in amounts_raw]

        if len(amounts) < 2:
            # If the row is clearly an item (has a date marker) but amounts are too garbled,
            # include it with zeroes so the operator can fill in the values manually.
            if has_date:
                data['items'].append({
                    'descrizione': desc,
                    'entrate': 0.0,
                    'uscite': 0.0,
                    'saldo': 0.0,
                })
            continue

        entrate = amounts[0]
        uscite  = amounts[1]

        data['items'].append({
            'descrizione': desc,
            'entrate': entrate,
            'uscite':  uscite,
            'saldo':   round(entrate - uscite, 2),
        })

    # Deduplica per nome esatto: se due foto si sovrappongono, un reparto può
    # comparire due volte. Si preferisce l'istanza con valori non-zero.
    seen: dict = {}
    for item in data['items']:
        name = item['descrizione']
        if name not in seen:
            seen[name] = item
        elif seen[name]['entrate'] == 0 and seen[name]['uscite'] == 0:
            seen[name] = item  # sostituisci lo zero con i dati reali
    data['items'] = list(seen.values())

    return data
