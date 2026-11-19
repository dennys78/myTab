"""Report giornaliero giacenze per n8n: sezioni + testo HTML spezzato (Telegram lo invia n8n)."""

from __future__ import annotations

import html
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .giacenze_stats import ESAURITO, PRIMA_CONSEGNA, calcola_giacenze
from .giacenze_views import _giorno_consegna_setting
from .tabacchi_preordine import _day, _decimal, prossimo_giorno_consegna
from .tabacchi_views import accoda_lettura
from .tabauno_portal import agent_is_online

MAX_TELEGRAM = 4000
GIORNI_IT = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')
CAMPI_RIGA = (
    'descrizione', 'aams', 'famiglia', 'tipo', 'giacenza', 'media',
    'stato', 'data_fine', 'mancanti_alla_data', 'giorni_fine',
)


def escape_html(value) -> str:
    return html.escape(str(value or ''), quote=False)


def formatta_data_corta(value) -> str:
    day = _day(value) if value else None
    if not day:
        return '—'
    return f'{GIORNI_IT[day.weekday()]} {day.day:02d}/{day.month:02d}'


def formatta_numero(value, digits=1) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return '—'
    if not (n == n):  # NaN
        return '—'
    testo = f'{n:.{digits}f}'.rstrip('0').rstrip('.')
    return testo.replace('.', ',')


def formatta_ora(letto_alle) -> str:
    if not letto_alle:
        return ''
    if isinstance(letto_alle, datetime):
        dt = letto_alle
    else:
        dt = parse_datetime(str(letto_alle))
    if not dt:
        return ''
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime('%H:%M')


def riga_pubblica(riga: dict) -> dict:
    return {campo: riga.get(campo) for campo in CAMPI_RIGA}


def sezioni_report(risultato: dict) -> tuple[list[dict], list[dict]]:
    """A) immancabili  B) non immancabili che finiscono prima di lunedì (media > 0)."""
    righe = [r for r in (risultato.get('righe') or []) if _decimal(r.get('media')) > 0]
    immancabili = [r for r in righe if r.get('immancabile')]
    ordine_stato = {ESAURITO: 0, PRIMA_CONSEGNA: 1}
    immancabili.sort(key=lambda r: (
        ordine_stato.get(r.get('stato'), 9),
        r['giorni_fine'] if r.get('giorni_fine') is not None else 10**9,
        r.get('descrizione') or '',
    ))
    prima = [
        r for r in righe
        if not r.get('immancabile') and int(r.get('mancanti_alla_data') or 0) > 0
    ]
    prima.sort(key=lambda r: (
        r.get('data_fine') or '9999-99-99',
        r.get('descrizione') or '',
    ))
    return immancabili, prima


def _riga_immancabile(riga: dict) -> str:
    nome = escape_html(riga.get('descrizione') or riga.get('aams') or '—')
    media = formatta_numero(riga.get('media'), 1)
    mancanti = int(riga.get('mancanti_alla_data') or 0)
    if riga.get('stato') == ESAURITO:
        return f'• {nome} – <b>ESAURITO</b> · {media}/gg · mancano {mancanti} pz a lun'
    giac = formatta_numero(riga.get('giacenza'), 0)
    fine = formatta_data_corta(riga.get('data_fine'))
    return f'• {nome} – giac {giac} · {media}/gg · finisce {fine} · mancano {mancanti} pz'


def _riga_prima(riga: dict) -> str:
    nome = escape_html(riga.get('descrizione') or riga.get('aams') or '—')
    giac = formatta_numero(riga.get('giacenza'), 0)
    media = formatta_numero(riga.get('media'), 1)
    fine = formatta_data_corta(riga.get('data_fine'))
    mancanti = int(riga.get('mancanti_alla_data') or 0)
    return f'• {nome} – giac {giac} · {media}/gg · finisce {fine} · mancano {mancanti} pz'


def costruisci_testo(
    *,
    oggi,
    lunedi,
    consegna,
    ultimo_giorno_chiuso,
    letto_alle,
    immancabili,
    prima_di_lunedi,
) -> str:
    chiusura = formatta_data_corta(ultimo_giorno_chiuso).split(' ', 1)[-1] if ultimo_giorno_chiuso else '—'
    ora = formatta_ora(letto_alle)
    meta = f'dati chiusura {chiusura}'
    if ora:
        meta += f', letti alle {ora}'
    linee = [
        f'📦 <b>Giacenze – {formatta_data_corta(oggi)}</b> ({meta})',
        f'Prossima consegna: {formatta_data_corta(consegna)}',
        '',
    ]
    if not immancabili and not prima_di_lunedi:
        linee.append('✅ Nessun articolo in esaurimento fino a lunedì')
        return '\n'.join(linee)

    linee.append(f'🔴 <b>IMMANCABILI ({len(immancabili)})</b>')
    if immancabili:
        linee.extend(_riga_immancabile(r) for r in immancabili)
    else:
        linee.append('✅ nessuna')

    linee.append(f'🟠 <b>FINISCONO PRIMA DI LUNEDÌ {formatta_data_corta(lunedi).split(" ", 1)[-1]} ({len(prima_di_lunedi)})</b>')
    if prima_di_lunedi:
        linee.extend(_riga_prima(r) for r in prima_di_lunedi)
    else:
        linee.append('✅ nessuna')
    return '\n'.join(linee)


def spezza_messaggi(testo: str, max_len: int = MAX_TELEGRAM) -> list[str]:
    """Spezza senza tagliare le righe; pezzi ≤ max_len."""
    if not testo:
        return ['']
    if len(testo) <= max_len:
        return [testo]
    linee = testo.split('\n')
    pezzi: list[str] = []
    corrente: list[str] = []
    lunghezza = 0
    for linea in linee:
        aggiunta = len(linea) + (1 if corrente else 0)
        if corrente and lunghezza + aggiunta > max_len:
            pezzi.append('\n'.join(corrente))
            corrente = [linea]
            lunghezza = len(linea)
        else:
            corrente.append(linea)
            lunghezza += aggiunta
    if corrente:
        pezzi.append('\n'.join(corrente))
    # Riga singola più lunga di max_len: spezza comunque (caso estremo).
    finali: list[str] = []
    for pezzo in pezzi:
        if len(pezzo) <= max_len:
            finali.append(pezzo)
            continue
        for i in range(0, len(pezzo), max_len):
            finali.append(pezzo[i:i + max_len])
    return finali or ['']


def messaggio_indisponibile(motivo: str) -> list[str]:
    testo = f'⚠️ <b>Report giacenze non disponibile</b>\n{escape_html(motivo)}'
    return spezza_messaggi(testo)


def corpo_da_lettura(payload: dict, oggi=None, *, giorno_consegna: int | None = None, company=None) -> dict:
    """Calcola sezioni + testo a partire dal payload TabaUno."""
    oggi = _day(oggi or timezone.localdate())
    if giorno_consegna is None:
        giorno_consegna = _giorno_consegna_setting(company) if company is not None else 0
    lunedi = prossimo_giorno_consegna(oggi, 0)
    consegna = prossimo_giorno_consegna(oggi, giorno_consegna)
    risultato = calcola_giacenze(
        payload,
        oggi,
        consegna=consegna,
        data_proiezione=lunedi,
        giorno_consegna=giorno_consegna,
    )
    immancabili, prima = sezioni_report(risultato)
    testo = costruisci_testo(
        oggi=oggi,
        lunedi=lunedi,
        consegna=consegna,
        ultimo_giorno_chiuso=payload.get('ultimo_giorno_chiuso'),
        letto_alle=payload.get('letto_alle'),
        immancabili=immancabili,
        prima_di_lunedi=prima,
    )
    messaggi = spezza_messaggi(testo)
    return {
        'data': oggi.isoformat(),
        'lunedi': lunedi.isoformat(),
        'consegna': consegna.isoformat(),
        'ultimo_giorno_chiuso': payload.get('ultimo_giorno_chiuso'),
        'letto_alle': payload.get('letto_alle') or '',
        'immancabili': [riga_pubblica(r) for r in immancabili],
        'prima_di_lunedi': [riga_pubblica(r) for r in prima],
        'testo': testo,
        'messaggi': messaggi,
    }


def esegui_report(company, *, attendi_lettura, timeout_offline='PC negozio offline'):
    """
    Lettura nuova + report. Restituisce (status_http, body).
    `attendi_lettura` è la callback stile n8n_tabacchi_views._attendi_lettura.
    """
    if not agent_is_online(company):
        messaggi = messaggio_indisponibile(timeout_offline)
        return 503, {'errore': timeout_offline, 'messaggi': messaggi, 'testo': messaggi[0]}

    lettura, _creata = accoda_lettura(company, None)
    lettura = attendi_lettura(lettura)
    if lettura is None or not isinstance(getattr(lettura, 'payload', None), dict):
        motivo = 'Lettura TabaUno non riuscita'
        messaggi = messaggio_indisponibile(motivo)
        return 503, {'errore': motivo, 'messaggi': messaggi, 'testo': messaggi[0]}

    body = corpo_da_lettura(lettura.payload, company=company)
    return 200, body
