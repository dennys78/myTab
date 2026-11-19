"""Report giornaliero giacenze per n8n: sezioni + testo HTML spezzato (Telegram lo invia n8n)."""

from __future__ import annotations

import html
import re
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .giacenze_stats import ESAURITO, PRIMA_CONSEGNA, calcola_giacenze
from .giacenze_views import _giorno_consegna_setting
from .tabacchi_preordine import FAMIGLIE, _day, _decimal, prossimo_giorno_consegna
from .tabacchi_views import accoda_lettura
from .tabauno_portal import agent_is_online

MAX_TELEGRAM = 4000
NOME_MAX = 32
GIORNI_IT = ('lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom')
CAMPI_RIGA = (
    'descrizione', 'aams', 'famiglia', 'tipo', 'giacenza', 'media',
    'stato', 'data_fine', 'mancanti_alla_data', 'giorni_fine',
)

_RE_DA20 = re.compile(r'\s+DA\s+20(?:\s+A\.?)?\s*$', re.IGNORECASE)
_RE_A_FINALE = re.compile(r'\s+A\.\s*$', re.IGNORECASE)
_RE_PREF_PLN = re.compile(r'^PLN[\s\-]*[A-Z0-9]+\s+', re.IGNORECASE)
_RE_PREF_AAMS = re.compile(r'^\d{2,10}\s+')  # solo codice numerico iniziale
_MINUS = '\u2212'  # −


def escape_html(value) -> str:
    return html.escape(str(value or ''), quote=False)


def formatta_data_corta(value) -> str:
    day = _day(value) if value else None
    if not day:
        return '—'
    return f'{GIORNI_IT[day.weekday()]} {day.day:02d}/{day.month:02d}'


def formatta_giorno_relativo(value, oggi) -> str:
    """Abbreviato (lun…) se entro 7 giorni da oggi, altrimenti gg/mm."""
    day = _day(value) if value else None
    if not day:
        return '—'
    oggi = _day(oggi)
    delta = (day - oggi).days
    if 0 <= delta <= 7:
        return GIORNI_IT[day.weekday()]
    return f'{day.day:02d}/{day.month:02d}'


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


def giacenza_mostrata(value) -> int:
    """Giacenze negative → 0."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return 0
    if not (n == n):
        return 0
    return max(0, int(n + (0.0000001 if n >= 0 else -0.0000001)))


def _title_case(testo: str) -> str:
    parti = []
    for parola in testo.split():
        if re.fullmatch(r'\d+[.,]\d+%?', parola) or re.fullmatch(r'\d+', parola):
            parti.append(parola)
            continue
        m = re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', parola)
        if not m:
            parti.append(parola)
            continue
        i = m.start()
        parti.append(parola[:i] + parola[i].upper() + parola[i + 1:].lower())
    return ' '.join(parti)


def nome_articolo(descrizione, aams=None, max_len: int = NOME_MAX) -> str:
    """Title Case, senza DA 20 A. / codice iniziale, max 32 caratteri."""
    nome = ' '.join(str(descrizione or '').split())
    if not nome and aams:
        nome = str(aams)
    code = str(aams or '').strip()
    if code and nome.upper().startswith(code.upper()):
        resto = nome[len(code):].lstrip(' \t-–—')
        if resto:
            nome = resto
    nome = _RE_PREF_PLN.sub('', nome)
    nome = _RE_PREF_AAMS.sub('', nome)
    nome = _RE_DA20.sub('', nome)
    nome = _RE_A_FINALE.sub('', nome)
    nome = ' '.join(nome.split())
    nome = _title_case(nome)
    if len(nome) > max_len:
        nome = nome[:max_len].rstrip(' -–—')
    return nome or '—'


def riga_pubblica(riga: dict) -> dict:
    return {campo: riga.get(campo) for campo in CAMPI_RIGA}


def _indice_famiglia(famiglia: str) -> int:
    try:
        return FAMIGLIE.index(famiglia)
    except ValueError:
        return len(FAMIGLIE)


def _ordina_sezione(righe: list[dict]) -> list[dict]:
    return sorted(righe, key=lambda r: (
        _indice_famiglia(r.get('famiglia') or ''),
        r.get('data_fine') or '9999-99-99',
        r.get('giorni_fine') if r.get('giorni_fine') is not None else 10**9,
        r.get('descrizione') or '',
    ))


def sezioni_report(risultato: dict) -> tuple[list[dict], list[dict]]:
    """A) immancabili  B) non immancabili che finiscono prima di lunedì (media > 0)."""
    esaurite, in_esaurimento, altre = sezioni_testo(risultato)
    immancabili = esaurite + in_esaurimento
    return immancabili, altre


def sezioni_testo(risultato: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Esaurite immancabili · immancabili in esaurimento · altre prima di lunedì."""
    righe = [r for r in (risultato.get('righe') or []) if _decimal(r.get('media')) > 0]
    esaurite = [
        r for r in righe
        if r.get('immancabile') and _decimal(r.get('giacenza')) <= 0
    ]
    in_esaurimento = [
        r for r in righe
        if r.get('immancabile') and _decimal(r.get('giacenza')) > 0
    ]
    altre = [
        r for r in righe
        if not r.get('immancabile') and int(r.get('mancanti_alla_data') or 0) > 0
    ]
    return _ordina_sezione(esaurite), _ordina_sezione(in_esaurimento), _ordina_sezione(altre)


def _mancanti_html(riga: dict) -> str:
    n = abs(int(riga.get('mancanti_alla_data') or 0))
    return f'<b>{_MINUS}{n} pz</b>'


def _dettaglio_esaurita(riga: dict) -> str:
    media = formatta_numero(riga.get('media'), 1)
    return f'   {media}/gg · {_mancanti_html(riga)} a lun'


def _dettaglio_in_esaurimento(riga: dict, oggi) -> str:
    giac = giacenza_mostrata(riga.get('giacenza'))
    media = formatta_numero(riga.get('media'), 1)
    fine = formatta_giorno_relativo(riga.get('data_fine'), oggi)
    return f'   giac {giac} · {media}/gg · finisce <b>{fine}</b> · {_mancanti_html(riga)}'


def _dettaglio_altra(riga: dict, oggi) -> str:
    media = formatta_numero(riga.get('media'), 1)
    if _decimal(riga.get('giacenza')) <= 0:
        return f'   <b>ESAURITO</b> · {media}/gg · {_mancanti_html(riga)}'
    giac = giacenza_mostrata(riga.get('giacenza'))
    fine = formatta_giorno_relativo(riga.get('data_fine'), oggi)
    return f'   giac {giac} · {media}/gg · finisce <b>{fine}</b> · {_mancanti_html(riga)}'


def blocco_articolo(riga: dict, *, stile: str, oggi) -> str:
    nome = escape_html(nome_articolo(riga.get('descrizione'), riga.get('aams')))
    if stile == 'esaurita':
        dettaglio = _dettaglio_esaurita(riga)
    elif stile == 'in_esaurimento':
        dettaglio = _dettaglio_in_esaurimento(riga, oggi)
    else:
        dettaglio = _dettaglio_altra(riga, oggi)
    return f'• {nome}\n{dettaglio}'


def _gruppi_famiglia(righe: list[dict]) -> list[tuple[str, list[dict]]]:
    gruppi: list[tuple[str, list[dict]]] = []
    corrente = None
    bucket: list[dict] = []
    for riga in righe:
        fam = riga.get('famiglia') or 'Altro'
        if fam != corrente:
            if bucket:
                gruppi.append((corrente, bucket))
            corrente = fam
            bucket = [riga]
        else:
            bucket.append(riga)
    if bucket:
        gruppi.append((corrente, bucket))
    return gruppi


def _struttura_sezione(titolo: str, stile: str, righe: list[dict], oggi) -> dict | None:
    if not righe:
        return None
    famiglie = []
    for fam, items in _gruppi_famiglia(righe):
        famiglie.append({
            'titolo': f'<b>{escape_html(fam)}</b>',
            'articoli': [blocco_articolo(r, stile=stile, oggi=oggi) for r in items],
        })
    return {'titolo': titolo, 'famiglie': famiglie}


def riepilogo_conteggi(esaurite, in_esaurimento, altre) -> str | None:
    pezzi = []
    if esaurite:
        n = len(esaurite)
        pezzi.append(f'🔴 <b>{n} esaurit{"a" if n == 1 else "e"}</b>')
    if in_esaurimento:
        pezzi.append(f'🟠 <b>{len(in_esaurimento)}</b> finiscono entro la consegna')
    if altre:
        pezzi.append(f'🟡 <b>{len(altre)}</b> altre prima di lunedì')
    return ' · '.join(pezzi) if pezzi else None


def _parti_report(*, oggi, consegna, letto_alle, esaurite, in_esaurimento, altre):
    prima = f'📦 <b>Giacenze – {formatta_data_corta(oggi)}</b>'
    ora = formatta_ora(letto_alle)
    if ora:
        prima += f' · letti alle {ora}'
    header = [
        prima,
        f'Consegna: <b>{formatta_data_corta(consegna)}</b>',
    ]
    if not esaurite and not in_esaurimento and not altre:
        header.append('✅ Nessun articolo in esaurimento fino a lunedì')
        return header, []

    riepilogo = riepilogo_conteggi(esaurite, in_esaurimento, altre)
    if riepilogo:
        header.append(riepilogo)

    sezioni = []
    for titolo, stile, righe in (
        ('🔴 <b>ESAURITE – IMMANCABILI</b>', 'esaurita', esaurite),
        ('🟠 <b>IMMANCABILI IN ESAURIMENTO</b>', 'in_esaurimento', in_esaurimento),
        ('🟡 <b>ALTRE PRIMA DI LUNEDÌ</b>', 'altra', altre),
    ):
        blocco = _struttura_sezione(titolo, stile, righe, oggi)
        if blocco:
            sezioni.append(blocco)
    return header, sezioni


def testo_continuo(header: list[str], sezioni: list[dict]) -> str:
    linee = list(header)
    for sezione in sezioni:
        linee.append(sezione['titolo'])
        for famiglia in sezione['famiglie']:
            linee.append(famiglia['titolo'])
            linee.extend(famiglia['articoli'])
    return '\n'.join(linee)


def costruisci_testo(
    *,
    oggi,
    lunedi=None,
    consegna,
    ultimo_giorno_chiuso=None,
    letto_alle,
    immancabili=None,
    prima_di_lunedi=None,
    esaurite=None,
    in_esaurimento=None,
    altre=None,
) -> str:
    """Compat: accetta le tre sezioni oppure immancabili+prima_di_lunedi."""
    if esaurite is None or in_esaurimento is None:
        imm = list(immancabili or [])
        esaurite = _ordina_sezione([r for r in imm if _decimal(r.get('giacenza')) <= 0])
        in_esaurimento = _ordina_sezione([r for r in imm if _decimal(r.get('giacenza')) > 0])
    if altre is None:
        altre = _ordina_sezione(list(prima_di_lunedi or []))

    header, sezioni = _parti_report(
        oggi=oggi,
        consegna=consegna,
        letto_alle=letto_alle,
        esaurite=esaurite,
        in_esaurimento=in_esaurimento,
        altre=altre,
    )
    return testo_continuo(header, sezioni)


def spezza_messaggi_strutturati(header: list[str], sezioni: list[dict], max_len: int = MAX_TELEGRAM) -> list[str]:
    """Spezza tra un articolo e l'altro; ripete intestazione sezione (+ famiglia) nel pezzo successivo."""
    header_txt = '\n'.join(header)
    if not sezioni:
        return [header_txt] if header_txt else ['']

    pezzi: list[str] = []
    buf = header_txt

    for sezione in sezioni:
        titolo_sez = sezione['titolo']
        need_sez = True
        for famiglia in sezione['famiglie']:
            titolo_fam = famiglia['titolo']
            need_fam = True
            for articolo in famiglia['articoli']:
                prefissi = []
                if need_sez:
                    prefissi.append(titolo_sez)
                if need_fam:
                    prefissi.append(titolo_fam)
                blocco = '\n'.join(prefissi + [articolo]) if prefissi else articolo
                candidato = f'{buf}\n{blocco}' if buf else blocco
                if buf and len(candidato) > max_len:
                    pezzi.append(buf)
                    buf = '\n'.join([titolo_sez, titolo_fam, articolo])
                else:
                    buf = candidato
                need_sez = False
                need_fam = False

    if buf:
        pezzi.append(buf)

    finali = []
    for pezzo in pezzi:
        if len(pezzo) <= max_len:
            finali.append(pezzo)
            continue
        for i in range(0, len(pezzo), max_len):
            finali.append(pezzo[i:i + max_len])
    return finali or ['']


def spezza_messaggi(testo: str, max_len: int = MAX_TELEGRAM) -> list[str]:
    """Fallback: spezza senza tagliare le righe (usato da messaggio_indisponibile)."""
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
    return pezzi or ['']


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
    esaurite, in_esaurimento, altre = sezioni_testo(risultato)
    immancabili = esaurite + in_esaurimento
    header, sezioni = _parti_report(
        oggi=oggi,
        consegna=consegna,
        letto_alle=payload.get('letto_alle'),
        esaurite=esaurite,
        in_esaurimento=in_esaurimento,
        altre=altre,
    )
    testo = testo_continuo(header, sezioni)
    messaggi = spezza_messaggi_strutturati(header, sezioni)
    return {
        'data': oggi.isoformat(),
        'lunedi': lunedi.isoformat(),
        'consegna': consegna.isoformat(),
        'ultimo_giorno_chiuso': payload.get('ultimo_giorno_chiuso'),
        'letto_alle': payload.get('letto_alle') or '',
        'immancabili': [riga_pubblica(r) for r in immancabili],
        'prima_di_lunedi': [riga_pubblica(r) for r in altre],
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
