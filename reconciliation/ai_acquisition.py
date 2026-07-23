"""Acquisizione IA multi-immagine: riepilogo cassa + report reparti (fino a 6 foto con Mooney)."""

from __future__ import annotations

from .closure_reports import REPORT_DEPARTMENTS, parse_amount
from .models import AppSetting

AI_ACQUISITION_MODE_TWO = 'two_files'
AI_ACQUISITION_MODE_FIVE = 'five_files'
VALID_AI_ACQUISITION_MODES = frozenset({AI_ACQUISITION_MODE_TWO, AI_ACQUISITION_MODE_FIVE})
AI_ACQUISITION_MIN_FILES = {
    AI_ACQUISITION_MODE_TWO: 2,
    AI_ACQUISITION_MODE_FIVE: 5,
}
AI_ACQUISITION_MAX_FILES = {
    AI_ACQUISITION_MODE_TWO: 2,
    AI_ACQUISITION_MODE_FIVE: 6,
}
# Report esterni (foto dedicate): ordine logico, non dipende dall'upload
REPORT_SLOT_ORDER = ('lottomatica', 'gratta', 'sisal')
OPTIONAL_REPORT_SLOTS = ('mooney',)
ALL_REPORT_SLOTS = REPORT_SLOT_ORDER + OPTIONAL_REPORT_SLOTS
DEPARTMENTS_FULL_REPORT_OVERLAY = frozenset({'lottomatica', 'sisal', 'mooney'})
FOOTER_SUMMARY_KEYS = (
    'contanti',
    'pag_pos',
    'cassa_auto',
    'reso_cont',
    'reso_auto',
    'distrib',
    'totale',
)

LOTTO_PROMPT = """Questa immagine è il report "Contabile Giornaliero" Lottomatica (Lotto, 10eLotto, MillionDAY, Fai3/Fai4).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = importo della riga "Entrate Gioco" in basso (es. +397,00 → 397.00)
- uscite = importo della riga "Uscite Gioco" in basso (es. 193,00 → 193.00)
- Estrai SEMPRE entrambi i totali finali Entrate Gioco / Uscite Gioco
- NON usare Aggio Gioco, Saldo, né le righe singole Importo giocate / Vincite pagate
- Numeri float positivi; se una riga non è leggibile usa 0.00"""

GRATTA_PROMPT = """Questa immagine è il report Gratta e Vinci "Premi pagati nel giorno" (tabella Gioco / Quantità / Importo).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"uscite": 0.00}

Regole:
- uscite = importo nella riga "Totale" in fondo alla tabella (es. € 120,00 → 120.00)
- NON usare singole righe gioco; solo il totale premi pagati del giorno.
- Numero float positivo; se non leggibile usa 0.00"""

SISAL_PROMPT = """Questa immagine è un report Sisal (BORDERÒ / MOVIMENTO CONTANTI, oppure tab RICONSEGNA/ESPOSIZIONE).
Può mostrare sezioni Win for Life, Ricariche, Super Win For Life e un riquadro TOTALE.
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = "Vendite" nel riquadro TOTALE (es. 127,50 → 127.50)
- uscite = valore assoluto di "Pagamenti" nel TOTALE (es. -12,27 → 12.27)
- Estrai SEMPRE entrate e uscite dal riquadro TOTALE, non dalle sezioni intermedie
- NON usare il saldo/netto finale in grande (es. 115,23); solo Vendite e Pagamenti del TOTALE
- Numeri float positivi; se non leggibile usa 0.00"""

MOONEY_PROMPT = """Questa immagine è la ricevuta Mooney "MOVIMENTO CONTANTE" (logo mooney in alto).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole:
- entrate = importo nella riga "Totale" in fondo (es. 444,92 → 444.92)
- uscite = 0.00 se il documento mostra solo "Incassato" (Ricariche e codici / Pagamenti e servizi)
- NON sommare a mano le sezioni Incassato se è già presente Totale
- Numeri float positivi; se non leggibile usa 0.00"""

REPORT_PROMPTS = {
    'lottomatica': LOTTO_PROMPT,
    'gratta': GRATTA_PROMPT,
    'sisal': SISAL_PROMPT,
    'mooney': MOONEY_PROMPT,
}

CLASSIFY_PROMPT = """Classifica questa immagine di documenti per una tabaccheria italiana.
Restituisci SOLO JSON: {"type": "main_closure"|"summary_footer"|"lottomatica"|"gratta"|"sisal"|"mooney"|"other"}

- main_closure: "Riepilogo Chiusure di Cassa" con tabella reparti (Tabacchi, Caffè, Gratta e Vinci, Pag fornitori, ecc.) e/o sezione "NUOVA SEZIONE GESTORI DI GIOCHI E SERVIZI" (LOTTOMATICA, MOONEY, SISAL con Entrate/Uscite/Saldo). Anche se in basso compare la riga Contanti/Pag.Pos/TOTALE, resta main_closure.
- summary_footer: SOLO (o quasi solo) la riga finale Contanti, Pag.Pos/Pag Pos, Cassa Auto, Reso Cont., Reso Auto, Distrib., TOTALE — senza righe reparto con Entrate/Uscite.
- lottomatica: "Contabile Giornaliero" con Lotto/10eLotto/MillionDAY e totali "Entrate Gioco" / "Uscite Gioco" (e Aggio/Saldo). NON è il riepilogo cassa POS.
- gratta: "Premi pagati nel giorno" Gratta e Vinci (Prospetti) con tabella Gioco/Quantità/Importo e riga Totale.
- sisal: schermata Sisal "BORDERÒ" / "MOVIMENTO CONTANTI" (UI gialla, calendario, Vendite/Pagamenti/TOTALE), oppure tab RICONSEGNA/ESPOSIZIONE. NON è la ricevuta cartacea Mooney.
- mooney: ricevuta con logo "mooney" e titolo "MOVIMENTO CONTANTE", sezioni Incassato e riga Totale.
- other: solo se non corrisponde a nessuna delle categorie sopra"""

CLASSIFY_BATCH_PROMPT = """Classifica ciascuna immagine nell'ordine in cui ti vengono inviate (immagine 1, 2, …).
Restituisci SOLO JSON con un array "types" della stessa lunghezza:
{"types": ["main_closure"|"summary_footer"|"lottomatica"|"gratta"|"sisal"|"mooney"|"other", ...]}

Regole di classificazione (obbligatorie):
- main_closure: Riepilogo Chiusure di Cassa / tabella reparti / NUOVA SEZIONE GESTORI (LOTTOMATICA, MOONEY, SISAL). Se ci sono Entrate/Uscite di reparto, NON usare summary_footer.
- summary_footer: SOLO riga Contanti, Pag.Pos, Cassa Auto, Resi, Distrib., TOTALE senza reparti.
- lottomatica: Contabile Giornaliero (Entrate Gioco / Uscite Gioco), non il foglio cassa.
- gratta: Premi pagati nel giorno Gratta e Vinci.
- sisal: BORDERÒ / MOVIMENTO CONTANTI Sisal (Vendite/Pagamenti). Non confondere con Mooney.
- mooney: ricevuta logo mooney MOVIMENTO CONTANTE.
- other: nessuno dei precedenti"""

VALID_IMAGE_TYPES = frozenset({
    'main_closure', 'summary_footer', 'lottomatica', 'gratta', 'sisal', 'mooney', 'other',
})

FIVE_FILES_SUMMARY_PROMPT = """Analizza l'immagine del RIEPILOGO FINALE CHIUSURA CASSA POS (riga con Contanti, Pag.Pos, Cassa Auto, Resi, Distrib., TOTALE).
Può essere solo la barra riepilogo o l'ultima riga sotto la tabella reparti.
Restituisci SOLO JSON valido, senza markdown:
{
  "date": "YYYY-MM-DD",
  "summary": {
    "contanti": 0.00,
    "pag_pos": 0.00,
    "cassa_auto": 0.00,
    "reso_cont": 0.00,
    "reso_auto": 0.00,
    "distrib": 0.00,
    "totale": 0.00
  }
}

Mappa le 7 colonne nell'ordine (esempio tipico: 0,00 | 431,10 | 1.841,85 | 0,00 | -5,00 | 306,40 | 2.579,35):
1. Contanti → contanti
2. Pag.Pos / Pagamento POS → pag_pos (NON è il totale)
3. Cassa Auto → cassa_auto
4. Reso Cont. → reso_cont
5. Reso Auto → reso_auto (può essere negativo, es. -5.00)
6. Distrib. / Distributore → distrib
7. TOTALE (ultima colonna) → totale

- Usa numeri decimali con punto (1841.85 non 1.841,85 nel JSON).
- reso_auto e reso_cont possono essere negativi; gli altri campi di solito ≥ 0.
- totale è SEMPRE l'ultima colonna etichettata TOTALE, mai Pag.Pos né Cassa Auto.
- Non sommare reparti: leggi solo la riga riepilogo.
- Data YYYY-MM-DD se visibile (es. 01/06/2026 → 2026-06-01), altrimenti stringa vuota."""


def get_ai_acquisition_file_mode(company) -> str:
    if not company:
        return AI_ACQUISITION_MODE_FIVE
    try:
        mode = AppSetting.objects.get(company=company, key='ai_acquisition_file_mode').value.strip()
    except AppSetting.DoesNotExist:
        return AI_ACQUISITION_MODE_FIVE
    return mode if mode in VALID_AI_ACQUISITION_MODES else AI_ACQUISITION_MODE_FIVE


def set_ai_acquisition_file_mode(company, mode: str) -> None:
    if not company:
        return
    mode = str(mode or '').strip()
    if mode not in VALID_AI_ACQUISITION_MODES:
        raise ValueError('Modalità acquisizione non valida')
    AppSetting.objects.update_or_create(
        company=company,
        key='ai_acquisition_file_mode',
        defaults={'value': mode},
    )


def max_acquisition_files_for_mode(mode: str) -> int:
    return AI_ACQUISITION_MAX_FILES.get(mode, 2)


def min_acquisition_files_for_mode(mode: str) -> int:
    return AI_ACQUISITION_MIN_FILES.get(mode, 1)


def is_valid_five_mode_file_count(count: int) -> bool:
    return int(count or 0) in (5, 6)


def validate_acquisition_file_count(company, count: int) -> None:
    mode = get_ai_acquisition_file_mode(company)
    count = int(count or 0)
    if count < 1:
        raise ValueError('Carica almeno un\'immagine.')
    if mode == AI_ACQUISITION_MODE_FIVE and not is_valid_five_mode_file_count(count):
        raise ValueError(
            f'Per l\'analisi a 5/6 file carica 5 immagini (standard) oppure 6 con report Mooney (ricevute {count}).'
        )
    if mode == AI_ACQUISITION_MODE_TWO and count > 2:
        raise ValueError(
            f'Per l\'analisi a 2 file carica al massimo 2 immagini (ricevute {count}).'
        )


def _summary_totale_value(summary: dict | None) -> float:
    if not isinstance(summary, dict):
        return 0.0
    return float(parse_amount(summary.get('totale', 0)))


def merge_five_files_summary(parsed: dict, footer_parsed: dict | None) -> dict:
    """Integra cassa auto, distributore, totale e resi dall'estrazione dedicata al riepilogo."""
    if not footer_parsed:
        return parsed
    merged = dict(parsed or {})
    main_summary = dict(merged.get('summary') or {})
    footer_summary = footer_parsed.get('summary') if isinstance(footer_parsed, dict) else {}
    if not isinstance(footer_summary, dict):
        footer_summary = {}

    footer_totale = _summary_totale_value(footer_summary)
    main_totale = _summary_totale_value(main_summary)
    prefer_footer = footer_totale > 0 and (
        main_totale <= 0 or abs(footer_totale - main_totale) >= 1
    )

    for key in FOOTER_SUMMARY_KEYS:
        from_footer = float(parse_amount(footer_summary.get(key, 0)))
        from_main = float(parse_amount(main_summary.get(key, 0)))
        if prefer_footer and (from_footer != 0 or key in ('totale', 'cassa_auto', 'distrib', 'pag_pos')):
            main_summary[key] = from_footer
        elif from_footer != 0 or from_main == 0:
            main_summary[key] = from_footer
        else:
            main_summary[key] = from_main

    merged['summary'] = main_summary
    if footer_parsed.get('date') and not merged.get('date'):
        merged['date'] = footer_parsed['date']
    return merged


def pick_best_footer_parsed(candidates: list[dict | None]) -> dict | None:
    best = None
    best_totale = 0.0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        summary = candidate.get('summary') or {}
        totale = _summary_totale_value(summary)
        cassa = float(parse_amount(summary.get('cassa_auto', 0)))
        score = totale + (cassa * 0.01 if totale <= 0 else 0)
        if score > best_totale:
            best = candidate
            best_totale = score
    return best


def normalize_image_type(raw: str) -> str:
    value = str(raw or '').strip().lower()
    return value if value in VALID_IMAGE_TYPES else 'other'


def split_acquisition_images_by_position(images: list) -> tuple[list, dict[str, dict], list]:
    """Fallback se la classificazione IA non è disponibile.

    Ordine atteso upload:
    - 6 foto: [main…] + Lottomatica, Mooney, Gratta, Sisal
    - 5 foto: [main…] + Lottomatica, Gratta, Sisal
    """
    n = len(images)
    if n == 6:
        report_keys = ('lottomatica', 'mooney', 'gratta', 'sisal')
        return list(images[:-4]), dict(zip(report_keys, images[-4:])), []
    if n == 5:
        main = list(images[:-3]) or [images[0]]
        slots = dict(zip(REPORT_SLOT_ORDER, images[-3:]))
        return main, slots, []
    if n >= 4:
        main = images[:-3]
        slots = dict(zip(REPORT_SLOT_ORDER, images[-3:]))
        return main, slots, []
    if n == 3:
        return images[:1], {'lottomatica': images[1], 'gratta': images[2]}, []
    return images, {}, []


def split_acquisition_images(
    images: list,
    image_types: list[str] | None = None,
) -> tuple[list, dict[str, dict], list]:
    """
    Separa riepilogo cassa, riga riepilogo (footer) e report giochi.
    Con image_types (da classificazione IA) non dipende dall'ordine di upload.
    """
    if not image_types or len(image_types) != len(images):
        return split_acquisition_images_by_position(images)

    main: list = []
    footer: list = []
    slots: dict[str, dict] = {}

    for image, img_type in zip(images, image_types):
        img_type = normalize_image_type(img_type)
        if img_type == 'summary_footer':
            footer.append(image)
        elif img_type == 'main_closure':
            main.append(image)
        elif img_type in ALL_REPORT_SLOTS and img_type not in slots:
            slots[img_type] = image

    if not main:
        # images sono dict (mime/b64): non hashabili → confronto per identità
        slot_ids = {id(img) for img in slots.values()}
        footer_ids = {id(img) for img in footer}
        main = [img for img in images if id(img) not in slot_ids and id(img) not in footer_ids]

    if not main and images:
        main = [images[0]]

    return main, slots, footer


def merge_report_overlays_into_items(items: list[dict], overlays: dict[str, dict]) -> list[dict]:
    """I report esterni sovrascrivono i reparti gioco nella maschera di acquisizione."""
    by_name = {item['descrizione']: item for item in items}
    gratta_dept = REPORT_DEPARTMENTS['gratta']

    for key, amounts in overlays.items():
        if key.startswith('_') or not amounts:
            continue
        dept = REPORT_DEPARTMENTS.get(key)
        if not dept:
            continue

        # Gratta e Vinci: entrate dal riepilogo cassa, uscite dal report premi
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

        # Lottomatica, Sisal, Mooney: sostituisci sempre entrate e uscite dal report dedicato
        if key in DEPARTMENTS_FULL_REPORT_OVERLAY:
            entrate = float(parse_amount(amounts.get('entrate', 0)))
            uscite = float(parse_amount(amounts.get('uscite', 0)))
            by_name[dept] = {
                'descrizione': dept,
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
        # Solo uscite dal report; le entrate restano dal riepilogo cassa
        return {'uscite': float(uscite)}
    entrate = parse_amount(parsed.get('entrate', 0))
    uscite = parse_amount(parsed.get('uscite', 0))
    if key in DEPARTMENTS_FULL_REPORT_OVERLAY:
        if entrate == 0 and uscite == 0:
            return None
        return {'entrate': float(entrate), 'uscite': float(uscite)}
    if entrate == 0 and uscite == 0:
        return None
    return {'entrate': float(entrate), 'uscite': float(uscite)}
