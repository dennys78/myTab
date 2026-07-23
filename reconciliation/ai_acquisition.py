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

LOTTO_PROMPT = """Questa immagine è il report "Contabile Giornaliero" Lottomatica
(menu Prospetti → Contabile giornaliero, tab Giochi Lotto).
Mostra conteggi giocate, importi (Importo giocate / Vincite pagate) e in basso i totali.

Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole OBBLIGATORIE — leggi SOLO queste due righe in fondo al documento:
- entrate = valore assoluto di "Entrate Gioco" (es. +397,00 → 397.00)
- uscite = valore assoluto di "Uscite Gioco" (es. 193,00 → 193.00)

VIETATO:
- NON usare "Aggio Gioco" (es. +31,76)
- NON usare "Saldo (Entrate - Aggio - Uscite)" (es. +172,24)
- NON sommare a mano le righe Importo giocate / Vincite pagate se Entrate Gioco e Uscite Gioco sono visibili
- NON usare i conteggi Num. giocate

Numeri float positivi; se una delle due righe non è leggibile usa 0.00.
Nota: se Uscite Gioco > Entrate Gioco il saldo (entrate-uscite) sarà negativo — è corretto, non invertire i valori."""

GRATTA_PROMPT = """Questa immagine è il report Gratta e Vinci "Premi pagati nel giorno" (tabella Gioco / Quantità / Importo).
Restituisci SOLO un oggetto JSON valido, senza markdown:
{"uscite": 0.00}

Regole:
- uscite = importo nella riga "Totale" in fondo alla tabella (es. € 120,00 → 120.00)
- NON usare singole righe gioco; solo il totale premi pagati del giorno.
- Numero float positivo; se non leggibile usa 0.00
- Nota: le Entrate restano dal riepilogo cassa; se i premi superano le entrate il saldo Gratta sarà negativo — è corretto."""

SISAL_PROMPT = """Questa immagine è il report Sisal "BORDERÒ" → tab "MOVIMENTO CONTANTI"
(calendario a sinistra, riquadro movimento a destra, pulsante STAMPA).

Restituisci SOLO un oggetto JSON valido, senza markdown:
{"entrate": 0.00, "uscite": 0.00}

Regole OBBLIGATORIE — leggi SOLO il riquadro "TOTALE" in basso nel borderò:
- entrate = importo "Vendite" nel TOTALE (es. 281,00 → 281.00)
- uscite = valore ASSOLUTO di "Pagamenti" nel TOTALE (es. -331,05 → 331.05)

VIETATO:
- NON usare il totale netto in grande in fondo (es. -50,05)
- NON usare le sezioni intermedie (Ricariche, Win for Life, Super Win For Life, ecc.)
- NON confondere con la ricevuta Mooney "MOVIMENTO CONTANTE"

Numeri float positivi; se una riga non è leggibile usa 0.00.
Nota: se Pagamenti > Vendite il saldo (entrate-uscite) sarà negativo (es. 281−331,05 = −50,05) — è corretto, non invertire né usare il netto al posto di Vendite/Pagamenti."""

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
- lottomatica: titolo "Contabile Giornaliero" (Prospetti / Giochi Lotto) con Num. giocate, Importo giocate, Vincite pagate e in basso "Entrate Gioco", "Aggio Gioco", "Uscite Gioco", "Saldo". Questa foto è la fonte ufficiale di LOTTOMATICA. NON è il riepilogo cassa POS.
- gratta: "Premi pagati nel giorno" Gratta e Vinci (Prospetti) con tabella Gioco/Quantità/Importo e riga Totale.
- sisal: schermata Sisal titolo "BORDERÒ", tab "MOVIMENTO CONTANTI" (o RICONSEGNA/ESPOSIZIONE), calendario, sezioni Vendite/Pagamenti e riquadro TOTALE. Fonte ufficiale SISAL. NON è la ricevuta cartacea Mooney.
- mooney: ricevuta con logo "mooney" e titolo "MOVIMENTO CONTANTE", sezioni Incassato e riga Totale.
- other: solo se non corrisponde a nessuna delle categorie sopra"""

CLASSIFY_BATCH_PROMPT = """Classifica ciascuna immagine nell'ordine in cui ti vengono inviate (immagine 1, 2, …).
Restituisci SOLO JSON con un array "types" della stessa lunghezza:
{"types": ["main_closure"|"summary_footer"|"lottomatica"|"gratta"|"sisal"|"mooney"|"other", ...]}

Regole di classificazione (obbligatorie):
- main_closure: Riepilogo Chiusure di Cassa / tabella reparti / NUOVA SEZIONE GESTORI (LOTTOMATICA, MOONEY, SISAL). Se ci sono Entrate/Uscite di reparto, NON usare summary_footer.
- summary_footer: SOLO riga Contanti, Pag.Pos, Cassa Auto, Resi, Distrib., TOTALE senza reparti.
- lottomatica: "Contabile Giornaliero" con Entrate Gioco / Aggio Gioco / Uscite Gioco / Saldo. Fonte ufficiale LOTTOMATICA. Non confondere con il foglio cassa.
- gratta: Premi pagati nel giorno Gratta e Vinci.
- sisal: "BORDERÒ" + "MOVIMENTO CONTANTI" Sisal (Vendite/Pagamenti nel TOTALE). Fonte ufficiale SISAL. Non confondere con Mooney.
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
            entrate = abs(float(parse_amount(existing.get('entrate', 0))))
            uscite = abs(float(parse_amount(amounts.get('uscite', 0))))
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
            entrate = abs(float(parse_amount(amounts.get('entrate', 0))))
            uscite = abs(float(parse_amount(amounts.get('uscite', 0))))
            by_name[dept] = {
                'descrizione': dept,
                'entrate': entrate,
                'uscite': uscite,
                'saldo': round(entrate - uscite, 2),
            }
            continue

        entrate = abs(float(parse_amount(amounts.get('entrate', 0))))
        uscite = abs(float(parse_amount(amounts.get('uscite', 0))))
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
        uscite = abs(parse_amount(parsed.get('uscite', 0)))
        if uscite == 0:
            return None
        # Solo uscite dal report; le entrate restano dal riepilogo cassa
        return {'uscite': float(uscite)}
    entrate = abs(parse_amount(parsed.get('entrate', 0)))
    uscite = abs(parse_amount(parsed.get('uscite', 0)))
    if key in DEPARTMENTS_FULL_REPORT_OVERLAY:
        if entrate == 0 and uscite == 0:
            return None
        return {'entrate': float(entrate), 'uscite': float(uscite)}
    if entrate == 0 and uscite == 0:
        return None
    return {'entrate': float(entrate), 'uscite': float(uscite)}


# ── Acquisizione unificata Gemini: 1 risposta XML → elaborazione locale ───────

UNIFIED_ACQUISITION_XML_PROMPT = """Ricevi N foto di una tabaccheria italiana (riepilogo cassa + report giochi).
Ogni foto è etichettata nel messaggio (IMG_1, IMG_2, …) con il ruolo atteso.

Restituisci SOLO un documento XML valido, senza markdown e senza testo fuori dal XML.
Schema obbligatorio:

<chiusura>
  <date>YYYY-MM-DD</date>
  <summary>
    <contanti>0.00</contanti>
    <pag_pos>0.00</pag_pos>
    <cassa_auto>0.00</cassa_auto>
    <reso_cont>0.00</reso_cont>
    <reso_auto>0.00</reso_auto>
    <distrib>0.00</distrib>
    <totale>0.00</totale>
  </summary>
  <items>
    <item descrizione="NOME" entrate="0.00" uscite="0.00"/>
  </items>
  <reports>
    <lottomatica entrate="0.00" uscite="0.00"/>
    <mooney entrate="0.00" uscite="0.00"/>
    <gratta uscite="0.00"/>
    <sisal entrate="0.00" uscite="0.00"/>
  </reports>
</chiusura>

Regole di lettura (OBBLIGATORIE):
1) Riepilogo cassa (main_closure): tutte le righe reparto con Entrate/Uscite (anche NUOVA SEZIONE GESTORI).
   summary = riga Contanti, Pag.Pos, Cassa Auto, Reso Cont., Reso Auto, Distrib., TOTALE (ultima colonna = totale).
2) Lottomatica (Contabile Giornaliero): SOLO Entrate Gioco e Uscite Gioco. VIETATO Aggio e Saldo.
3) Sisal (BORDERÒ MOVIMENTO CONTANTI): SOLO Vendite e |Pagamenti| del riquadro TOTALE. VIETATO il netto.
4) Mooney (MOVIMENTO CONTANTE): Totale ricevuta in entrate; uscite 0 se non ci sono pagamenti espliciti.
5) Gratta (Premi pagati): solo Totale premi in uscite (attributo uscite). Le entrate Gratta restano dal riepilogo.
6) Numeri con punto decimale (397.00). Valori assoluti positivi per entrate/uscite.
7) Se un report non è presente tra le foto, lascia 0.00. Non inventare.
8) descrizioni reparto in MAIUSCOLO.
"""


def build_unified_image_roles(image_count: int) -> list[str]:
    """Etichette ruolo per ordine upload (allineato a split_acquisition_images_by_position)."""
    n = int(image_count or 0)
    if n <= 0:
        return []
    if n >= 6:
        return ['main_closure'] * (n - 4) + ['lottomatica', 'mooney', 'gratta', 'sisal']
    if n == 5:
        return ['main_closure'] * (n - 3) + ['lottomatica', 'gratta', 'sisal']
    if n >= 3:
        return ['main_closure'] * (n - 3) + list(REPORT_SLOT_ORDER)
    return ['main_closure'] * n


def _xml_text(el, default=''):
    if el is None or el.text is None:
        return default
    return str(el.text).strip()


def parse_unified_acquisition_xml(raw: str) -> dict:
    """Parsa XML Gemini → dict locale {date, summary, items, overlays}."""
    import re
    import xml.etree.ElementTree as ET

    text = (raw or '').strip()
    if not text:
        raise ValueError('Risposta XML Gemini vuota.')

    # Togli eventuali fence markdown
    fence = re.search(r'```(?:xml)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    start = text.find('<chiusura')
    end = text.rfind('</chiusura>')
    if start >= 0 and end > start:
        text = text[start:end + len('</chiusura>')]

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError(f'XML Gemini non valido: {exc}') from exc

    if root.tag.lower() != 'chiusura':
        # prova figlio
        found = root.find('.//chiusura')
        if found is None:
            raise ValueError('XML senza elemento <chiusura>.')
        root = found

    date = _xml_text(root.find('date'))
    summary = {}
    summary_el = root.find('summary')
    if summary_el is not None:
        for key in FOOTER_SUMMARY_KEYS:
            child = summary_el.find(key)
            if child is not None:
                summary[key] = float(parse_amount(_xml_text(child, '0') or child.get(key) or 0))

    items = []
    items_el = root.find('items')
    if items_el is not None:
        for item_el in items_el.findall('item'):
            desc = (
                item_el.get('descrizione')
                or _xml_text(item_el.find('descrizione'))
                or ''
            ).strip()
            if not desc:
                continue
            entrate = abs(float(parse_amount(
                item_el.get('entrate') or _xml_text(item_el.find('entrate'), '0')
            )))
            uscite = abs(float(parse_amount(
                item_el.get('uscite') or _xml_text(item_el.find('uscite'), '0')
            )))
            items.append({
                'descrizione': desc.upper(),
                'entrate': entrate,
                'uscite': uscite,
                'saldo': round(entrate - uscite, 2),
            })

    overlays = {}
    reports_el = root.find('reports')
    if reports_el is not None:
        for key in ALL_REPORT_SLOTS:
            el = reports_el.find(key)
            if el is None:
                continue
            raw_overlay = {
                'entrate': el.get('entrate') or _xml_text(el.find('entrate'), '0'),
                'uscite': el.get('uscite') or _xml_text(el.find('uscite'), '0'),
            }
            normalized = normalize_report_overlay(key, raw_overlay)
            if normalized:
                overlays[key] = normalized

    return {
        'date': date,
        'summary': summary,
        'items': items,
        'overlays': overlays,
        'slot_strategy': 'unified_xml',
    }
