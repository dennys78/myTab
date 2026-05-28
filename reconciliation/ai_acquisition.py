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

SISAL_PROMPT = """Questa immagine è un report Sisal "Movimento contanti" BORDERÒ o riepilogo PDV Sisal.
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = riga "Totale vendite" / "Vendite" nel riquadro TOTALE (es. 77,00)
- uscite = valore assoluto di "Pagamenti" nel TOTALE (es. -5,21 → 5.21)
- Ignora il netto finale; usa solo vendite e pagamenti.
- Numeri float positivi; se non leggibile usa 0.00"""

REPORT_PROMPTS = {
    'lottomatica': LOTTO_PROMPT,
    'gratta': GRATTA_PROMPT,
    'sisal': SISAL_PROMPT,
}

CLASSIFY_PROMPT = """Classifica questa immagine di documenti per una tabaccheria italiana.
Restituisci SOLO JSON: {"type": "main_closure"|"lottomatica"|"gratta"|"sisal"|"other"}

- main_closure: tabella "Riepilogo Chiusure di Cassa" con reparti (Tabacchi, Caffè, Gratta e Vinci, Lottomatica, Mooney, Sisal, ecc.)
- lottomatica: Contabile Giornaliero / Prospetto con "Entrate Gioco" e "Uscite Gioco"
- gratta: "Premi pagati nel giorno" / prospetto Gratta e Vinci
- sisal: BORDERÒ "Movimento contanti" con Totale vendite e Pagamenti (Sisal / ricariche)
- other: anteprima generica non classificabile"""

VALID_IMAGE_TYPES = frozenset({'main_closure', 'lottomatica', 'gratta', 'sisal', 'other'})


def normalize_image_type(raw: str) -> str:
    value = str(raw or '').strip().lower()
    return value if value in VALID_IMAGE_TYPES else 'other'


def split_acquisition_images_by_position(images: list) -> tuple[list, dict[str, dict]]:
    """Fallback se la classificazione IA non è disponibile."""
    n = len(images)
    if n >= 4:
        main = images[:-3]
        slots = dict(zip(REPORT_SLOT_ORDER, images[-3:]))
        return main, slots
    if n == 3:
        return images[:1], {'lottomatica': images[1], 'gratta': images[2]}
    return images, {}


def split_acquisition_images(images: list, image_types: list[str] | None = None) -> tuple[list, dict[str, dict]]:
    """
    Separa riepilogo cassa e report giochi.
    Con image_types (da classificazione IA) non dipende dall'ordine di upload.
    """
    if not image_types or len(image_types) != len(images):
        return split_acquisition_images_by_position(images)

    main: list = []
    slots: dict[str, dict] = {}

    for image, img_type in zip(images, image_types):
        img_type = normalize_image_type(img_type)
        if img_type == 'main_closure':
            main.append(image)
        elif img_type in REPORT_SLOT_ORDER and img_type not in slots:
            slots[img_type] = image

    if not main:
        slot_images = set(slots.values())
        main = [img for img in images if img not in slot_images]

    if not main and images:
        main = [images[0]]

    return main, slots


def merge_report_overlays_into_items(items: list[dict], overlays: dict[str, dict]) -> list[dict]:
    """I report esterni (foto 3–5) sovrascrivono i reparti gioco."""
    by_name = {item['descrizione']: item for item in items}
    gratta_dept = REPORT_DEPARTMENTS['gratta']

    for key, amounts in overlays.items():
        if not amounts:
            continue
        dept = REPORT_DEPARTMENTS.get(key)
        if not dept:
            continue

        # Gratta e Vinci: entrate dal riepilogo cassa (foto 1), uscite dal report premi (foto 4)
        if key == 'gratta':
            existing = by_name.get(gratta_dept, {})
            entrate = float(parse_amount(existing.get('entrate', 0)))
            uscite = float(parse_amount(amounts.get('uscite', 0)))
            if entrate == 0 and uscite == 0:
                continue
            by_name[gratta_dept] = {
                'descrizione': gratta_dept,
                'entrate': entrate,
                'uscite': uscite,
                'saldo': round(entrate - uscite, 2),
            }
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
        # Solo uscite dal report; le entrate restano dal riepilogo cassa (foto 1)
        return {'uscite': float(uscite)}
    entrate = parse_amount(parsed.get('entrate', 0))
    uscite = parse_amount(parsed.get('uscite', 0))
    if entrate == 0 and uscite == 0:
        return None
    return {'entrate': float(entrate), 'uscite': float(uscite)}
