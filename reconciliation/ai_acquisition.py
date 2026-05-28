"""Acquisizione IA multi-immagine: riepilogo cassa + report reparti (foto 3–5)."""

from __future__ import annotations

from .closure_reports import REPORT_DEPARTMENTS, parse_amount

# Ultime 3 foto (ordine upload): Lottomatica, Gratta e Vinci, Sisal
REPORT_SLOT_ORDER = ('lottomatica', 'gratta', 'sisal')

LOTTO_PROMPT = """Questa immagine è un report Contabile Giornaliero Lottomatica (tabaccheria).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = importo della riga "Entrate Gioco" (o Entrate gioco / Entrate Giochi)
- uscite = importo della riga "Uscite Gioco" (o Uscite gioco)
- Numeri float positivi; se non leggibile usa 0.00"""

GRATTA_PROMPT = """Questa immagine è un report Gratta e Vinci (premi pagati nel giorno).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"uscite": 0.00}

Regole:
- uscite = totale "Premi pagati nel giorno" (o Premi pagati / totale premi pagati)
- Numero float positivo; se non leggibile usa 0.00"""

SISAL_PROMPT = """Questa immagine è un report Sisal "Movimento contanti" o riepilogo PDV Sisal.
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = "Totale vendite" (vendite contanti)
- uscite = "Pagamenti"
- Numeri float positivi; se non leggibile usa 0.00"""

REPORT_PROMPTS = {
    'lottomatica': LOTTO_PROMPT,
    'gratta': GRATTA_PROMPT,
    'sisal': SISAL_PROMPT,
}


def split_acquisition_images(images: list) -> tuple[list, dict[str, dict]]:
    """
    Con 4+ immagini: le ultime 3 sono Lottomatica, Gratta, Sisal (in ordine).
    Le precedenti sono il riepilogo cassa POS.
  Con 3 immagini: [0]=cassa, [1]=Lottomatica, [2]=Gratta.
    """
    n = len(images)
    if n >= 4:
        main = images[:-3]
        slots = dict(zip(REPORT_SLOT_ORDER, images[-3:]))
        return main, slots
    if n == 3:
        return images[:1], {'lottomatica': images[1], 'gratta': images[2]}
    return images, {}


def merge_report_overlays_into_items(items: list[dict], overlays: dict[str, dict]) -> list[dict]:
    """I report esterni (foto 3–5) sovrascrivono i reparti gioco."""
    by_name = {item['descrizione']: item for item in items}

    for key, amounts in overlays.items():
        if not amounts:
            continue
        dept = REPORT_DEPARTMENTS.get(key)
        if not dept:
            continue
        entrate = float(parse_amount(amounts.get('entrate', 0)))
        uscite = float(parse_amount(amounts.get('uscite', 0)))
        if entrate == 0 and uscite == 0:
            continue
        by_name[dept] = {
            'descrizione': dept,
            'entrate': entrate,
            'uscite': uscite,
            'saldo': round(entrate - uscite, 2),
        }

    return list(by_name.values())


def normalize_report_overlay(key: str, parsed: dict) -> dict | None:
    if not isinstance(parsed, dict):
        return None
    if key == 'gratta':
        uscite = parse_amount(parsed.get('uscite', 0))
        if uscite == 0:
            return None
        return {'entrate': 0, 'uscite': float(uscite)}
    entrate = parse_amount(parsed.get('entrate', 0))
    uscite = parse_amount(parsed.get('uscite', 0))
    if entrate == 0 and uscite == 0:
        return None
    return {'entrate': float(entrate), 'uscite': float(uscite)}
