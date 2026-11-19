"""Client del servizio locale «logista» (Mac mini): carica l'ordine nella proposta WebT e lo invia.

/logista/invia non va mai ripetuto in automatico: un secondo tentativo può generare un doppio ordine.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import close_old_connections
from django.utils import timezone

from .models import LogistaInvioJob
from .tabacchi_preordine import righe_export_logista

logger = logging.getLogger(__name__)

DEFAULT_URL = 'http://host.docker.internal:3501'
CARICA_TIMEOUT = 20 * 60
INVIA_TIMEOUT = 5 * 60
SECONDI_PER_RIGA = 3
JOB_SCADUTO = timedelta(minutes=30)
N8N_TIMEOUT = 20
N8N_TENTATIVI = 2
TELEGRAM_CAPTION_MAX = 1024
FAMIGLIE_ALTRI = ('Dispositivi', 'Solidi')
STATI_FINALI = LogistaInvioJob.STATI_FINALI
STATI_IN_CORSO = LogistaInvioJob.STATI_IN_CORSO

FASE_CARICAMENTO = 'caricamento'
FASE_INVIO = 'invio'
VERIFICA_WEBT = "verificare su WebT se l'ordine è partito prima di reinviarlo"


class LogistaServiceError(RuntimeError):
    def __init__(self, messaggio: str, *, sicuro: bool = True):
        super().__init__(messaggio)
        # sicuro=False: la richiesta potrebbe essere arrivata al servizio (esito sconosciuto).
        self.sicuro = sicuro


def logista_config():
    url = (os.environ.get('LOGISTA_SERVICE_URL') or DEFAULT_URL).strip().rstrip('/')
    key = (os.environ.get('LOGISTA_SERVICE_KEY') or '').strip()
    return url, key


def logista_configurato() -> bool:
    return bool(logista_config()[1])


def righe_logista_payload(righe):
    """Stesse righe di Ordine_Logista.xls, nel formato del servizio."""
    return [{'codice': codice, 'qta': qta} for codice, qta in righe_export_logista(righe)]


def _messaggio_http(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode('utf-8', errors='replace') or '{}')
    except (ValueError, OSError):
        body = {}
    dettaglio = str(body.get('errore') or '').strip() if isinstance(body, dict) else ''
    if exc.code == 409:
        return 'Servizio Logista occupato: un\'altra operazione è in corso. Riprova tra qualche minuto.'
    if exc.code in (401, 403):
        return 'Servizio Logista: chiave non valida.'
    return f'Servizio Logista ha risposto {exc.code}' + (f': {dettaglio}' if dettaglio else '.')


def _posta(url: str, key: str, percorso: str, corpo: dict, timeout: int) -> dict:
    richiesta = urllib.request.Request(
        f'{url}{percorso}',
        data=json.dumps(corpo).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'x-api-key': key,
            'User-Agent': 'myTaba-Logista/1.0',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as response:
            body = response.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as exc:
        sicuro = exc.code in (401, 403, 409) or exc.code < 500
        raise LogistaServiceError(_messaggio_http(exc), sicuro=sicuro) from exc
    except urllib.error.URLError as exc:
        rifiutata = isinstance(exc.reason, ConnectionRefusedError)
        if isinstance(exc.reason, TimeoutError):
            raise LogistaServiceError(
                f'Servizio Logista: tempo scaduto ({timeout // 60} minuti).', sicuro=False,
            ) from exc
        raise LogistaServiceError(
            'Servizio Logista non raggiungibile sul Mac mini (porta 3501).', sicuro=rifiutata,
        ) from exc
    except (TimeoutError, OSError) as exc:
        raise LogistaServiceError(
            f'Servizio Logista: tempo scaduto ({timeout // 60} minuti).', sicuro=False,
        ) from exc
    try:
        data = json.loads(body or '{}')
    except ValueError as exc:
        raise LogistaServiceError('Servizio Logista: risposta non valida.', sicuro=False) from exc
    if not isinstance(data, dict):
        raise LogistaServiceError('Servizio Logista: risposta non valida.', sicuro=False)
    return data


def posta_carica(url: str, key: str, righe: list, svuota: bool, timeout: int = CARICA_TIMEOUT) -> dict:
    return _posta(url, key, '/logista/carica', {'righe': righe, 'svuota': bool(svuota)}, timeout)


def posta_invia(url: str, key: str, timeout: int = INVIA_TIMEOUT) -> dict:
    return _posta(url, key, '/logista/invia', {'conferma': True}, timeout)


def salva_foto(job_id: int, foto_b64: str, suffisso: str = '') -> str:
    if not foto_b64:
        return ''
    try:
        data = base64.b64decode(foto_b64, validate=False)
    except (ValueError, TypeError):
        return ''
    if not data:
        return ''
    rel = f'logista/{job_id}{suffisso}.jpg'
    path = Path(settings.MEDIA_ROOT) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def _senza_foto(data: dict) -> dict:
    return {k: v for k, v in data.items() if k != 'foto_jpeg_base64'}


def applica_risposta(job: LogistaInvioJob, data: dict) -> bool:
    """Esito di /logista/carica. True se si può procedere con l'invio."""
    job.fase = FASE_CARICAMENTO
    if data.get('errore'):
        job.stato = LogistaInvioJob.ERRORE
        job.errore = str(data.get('errore'))[:2000]
        return False
    esito = data.get('esito')
    if esito == 'proposta_non_vuota':
        job.stato = LogistaInvioJob.ATTESA_CONFERMA
        try:
            job.righe_presenti = int(data.get('righe_presenti') or 0)
        except (TypeError, ValueError):
            job.righe_presenti = 0
        job.risultato = {'esito': esito, 'righe_presenti': job.righe_presenti}
        return False
    if esito == 'caricato':
        job.foto_path = salva_foto(job.id, data.get('foto_jpeg_base64') or '')
        job.risultato = _senza_foto(data)
        job.errore = ''
        try:
            inserite = int(data.get('inserite') or 0)
        except (TypeError, ValueError):
            inserite = 0
        if inserite <= 0:
            job.stato = LogistaInvioJob.NON_INVIATO
            job.errore = 'Nessuna riga accettata da Logista.'
            return False
        return True
    job.stato = LogistaInvioJob.ERRORE
    job.errore = f'Servizio Logista: esito non previsto ({esito or "vuoto"}).'
    return False


def applica_invio(job: LogistaInvioJob, data: dict) -> None:
    """Esito di /logista/invia."""
    risultato = dict(job.risultato or {})
    risultato['invio'] = _senza_foto(data)
    job.risultato = risultato
    job.foto_invio_path = salva_foto(job.id, data.get('foto_jpeg_base64') or '', '_invio')
    esito = data.get('esito')
    if esito == 'inviato':
        job.stato = LogistaInvioJob.INVIATO
        job.fase = FASE_INVIO
        job.codice_ordine = str(data.get('codice_ordine') or '')[:64]
        job.data_consegna_logista = str(data.get('data_consegna') or '')[:16]
        job.errore = ''
        return
    if esito == 'bloccato':
        job.stato = LogistaInvioJob.NON_INVIATO
        job.fase = str(data.get('fase') or FASE_INVIO)[:32]
        job.errore = str(data.get('messaggio') or 'Invio bloccato su WebT.')[:2000]
        return
    if esito == 'incerto':
        job.stato = LogistaInvioJob.NON_INVIATO
        job.fase = 'incerto'
        messaggio = str(data.get('messaggio') or 'Esito dell\'invio non verificabile.').strip()
        job.errore = f'{messaggio} — Esito INCERTO: {VERIFICA_WEBT}.'[:2000]
        return
    job.stato = LogistaInvioJob.ERRORE
    job.fase = FASE_INVIO
    dettaglio = data.get('errore') or f'esito non previsto ({esito or "vuoto"})'
    job.errore = f'Invio non confermato: {dettaglio}. Da {VERIFICA_WEBT}.'[:2000]


def n8n_tabacchi_config():
    url = os.environ.get('N8N_TABACCHI_WEBHOOK_URL', '').strip()
    token = (
        os.environ.get('N8N_TABACCHI_TOKEN', '').strip()
        or os.environ.get('N8N_GRATTA_TOKEN', '').strip()
    )
    return url, token


def riepilogo_preordine(preordine) -> dict:
    if preordine is None:
        return {'kg_tabacco': 0.0, 'pezzi_altri': 0, 'valore_stimato': 0.0}
    pezzi_altri = sum(
        int(riga.unita)
        for riga in preordine.righe.filter(unita__gt=0, famiglia__in=FAMIGLIE_ALTRI)
    )
    return {
        'kg_tabacco': float(preordine.kg or 0),
        'pezzi_altri': pezzi_altri,
        'valore_stimato': float(preordine.totale or 0),
    }


def _foto_bytes(rel: str) -> bytes:
    if not rel:
        return b''
    path = Path(settings.MEDIA_ROOT) / rel
    return path.read_bytes() if path.is_file() else b''


def foto_esito(job: LogistaInvioJob) -> bytes:
    """Foto da allegare: quella dell'invio (o del blocco), altrimenti quella del caricamento."""
    return _foto_bytes(job.foto_invio_path) or _foto_bytes(job.foto_path)


def _invio(job: LogistaInvioJob) -> dict:
    return (job.risultato or {}).get('invio') or {}


def payload_n8n(job: LogistaInvioJob) -> dict:
    risultato = job.risultato or {}
    proposta = risultato.get('proposta') or {}
    invio = _invio(job)
    payload = {
        'evento': 'logista_caricato',
        'job_id': job.id,
        'stato': job.stato,
        'origine': job.origine,
        'righe_inviate': job.righe_inviate,
        'inserite': risultato.get('inserite') or 0,
        'rifiutate': risultato.get('rifiutate') or [],
        'avvisi': risultato.get('avvisi') or [],
        'proposta': {'tabacchi': proposta.get('tabacchi'), 'altri': proposta.get('altri')},
        **riepilogo_preordine(job.preordine),
    }
    if job.stato == LogistaInvioJob.ATTESA_CONFERMA:
        payload['righe_presenti'] = job.righe_presenti or 0
    if job.stato == LogistaInvioJob.INVIATO:
        payload['codice_ordine'] = job.codice_ordine
        payload['data_consegna'] = job.data_consegna_logista
        payload['totali'] = invio.get('totali') or []
    if job.stato in (LogistaInvioJob.NON_INVIATO, LogistaInvioJob.ERRORE):
        payload['fase'] = job.fase
        payload['errore'] = job.errore
    if job.stato in (LogistaInvioJob.INVIATO, LogistaInvioJob.NON_INVIATO):
        foto = foto_esito(job)
        if foto:
            payload['foto_jpeg_base64'] = base64.b64encode(foto).decode('ascii')
    return payload


def notifica_n8n(job: LogistaInvioJob) -> bool:
    """POST dell'esito a n8n (stesso header x-api-key del webhook Gratta). Errori solo loggati."""
    if job.stato not in STATI_FINALI:
        return False
    url, token = n8n_tabacchi_config()
    if not url:
        return False
    try:
        raw = json.dumps(payload_n8n(job)).encode('utf-8')
    except Exception:
        logger.exception('notifica n8n tabacchi job %s: payload non costruibile', job.id)
        return False
    for tentativo in range(1, N8N_TENTATIVI + 1):
        richiesta = urllib.request.Request(
            url,
            data=raw,
            headers={
                'Content-Type': 'application/json',
                'x-api-key': token,
                'User-Agent': 'myTaba-Tabacchi/1.0',
            },
            method='POST',
        )
        try:
            with urllib.request.urlopen(richiesta, timeout=N8N_TIMEOUT) as response:
                response.read()
            return True
        except urllib.error.HTTPError as exc:
            motivo = f'HTTP {exc.code}'
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            motivo = type(exc).__name__
        logger.warning(
            'notifica n8n tabacchi job %s fallita (tentativo %s/%s): %s',
            job.id, tentativo, N8N_TENTATIVI, motivo,
        )
    return False


def _kg_testo(kg: float) -> str:
    return f'{kg:.3f}'.rstrip('0').rstrip('.').replace('.', ',') or '0'


def _euro_testo(valore: float) -> str:
    return f'{valore:,.2f} €'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _righe_rifiutate(job: LogistaInvioJob) -> list[str]:
    out = []
    for riga in (job.risultato or {}).get('rifiutate') or []:
        if not isinstance(riga, dict):
            continue
        out.append(f"• {riga.get('codice', '')} {riga.get('qta', '')} → {riga.get('errore') or 'rifiutata'}")
    return out


def testo_telegram(job: LogistaInvioJob) -> str:
    riepilogo = riepilogo_preordine(job.preordine)
    risultato = job.risultato or {}
    rifiutate = _righe_rifiutate(job)
    if job.stato == LogistaInvioJob.INVIATO:
        totali = [str(t).strip() for t in (_invio(job).get('totali') or []) if str(t).strip()]
        importo = ' · '.join(totali) if totali else f"{_euro_testo(riepilogo['valore_stimato'])} (stima myTaba)"
        righe = [
            '✅ Ordine Logista INVIATO',
            f"Codice ordine: {job.codice_ordine or '—'}   Consegna: {job.data_consegna_logista or '—'}",
            f"Tabacco: {_kg_testo(riepilogo['kg_tabacco'])} kg · Altri prodotti: {riepilogo['pezzi_altri']} pz",
            f'Importo: {importo}',
            f"Righe inserite: {risultato.get('inserite') or 0}/{job.righe_inviate}",
        ]
        if rifiutate:
            righe.append('Righe rifiutate:')
            righe.extend(rifiutate)
        return '\n'.join(righe)

    if job.stato == LogistaInvioJob.ATTESA_CONFERMA:
        fase = FASE_CARICAMENTO
        motivo = f'su WebT c\'è già una proposta con {job.righe_presenti or 0} righe.'
        chiusura = 'Apri Ordine Tabacchi in myTaba e scegli «Svuota e carica».'
    else:
        fase = job.fase or FASE_CARICAMENTO
        motivo = job.errore or 'motivo non disponibile'
        if fase == 'incerto':
            chiusura = f'ATTENZIONE: {VERIFICA_WEBT}.'
        elif fase == FASE_CARICAMENTO and not risultato.get('inserite'):
            chiusura = 'Nessun ordine inviato: controlla la proposta su WebT.'
        else:
            chiusura = 'La proposta caricata è rimasta su WebT: controlla e invia a mano.'
    righe = [
        '⚠️ Ordine Logista NON inviato',
        f'Fase: {fase}  Motivo: {motivo}',
        chiusura,
    ]
    if rifiutate:
        righe.append('Righe rifiutate:')
        righe.extend(rifiutate)
    return '\n'.join(righe)


def notifica_telegram(job: LogistaInvioJob) -> int:
    """Riepilogo sul bot Telegram di myTaba (stesse chat delle altre notifiche)."""
    from .draft_notifications import (
        _get_telegram_chat_ids,
        _get_telegram_token,
        _send_telegram_message,
        send_telegram_photo,
    )

    if job.stato not in STATI_FINALI:
        return 0
    token = _get_telegram_token(job.company)
    if not token:
        return 0
    testo = testo_telegram(job)
    foto = foto_esito(job)
    inviati = 0
    for chat_id in _get_telegram_chat_ids(job.company):
        try:
            if foto and len(testo) <= TELEGRAM_CAPTION_MAX:
                ok = send_telegram_photo(token, chat_id, foto, caption=testo)
            else:
                ok = _send_telegram_message(token, chat_id, testo)
                if ok and foto:
                    send_telegram_photo(token, chat_id, foto)
            if not ok and foto:
                ok = _send_telegram_message(token, chat_id, testo)
            inviati += int(bool(ok))
        except Exception as exc:
            logger.warning('Telegram esito Logista job %s fallito per chat %s: %s', job.id, chat_id, type(exc).__name__)
    return inviati


def _notifica_sicura(job_id: int) -> None:
    try:
        job = LogistaInvioJob.objects.select_related('preordine', 'company').get(id=job_id)
    except Exception:
        logger.exception('notifiche job Logista %s: job non leggibile', job_id)
        return
    for notifica in (notifica_telegram, notifica_n8n):
        try:
            notifica(job)
        except Exception:
            logger.exception('notifica %s job Logista %s non riuscita', notifica.__name__, job_id)


def _errore_invio(exc: LogistaServiceError) -> str:
    if exc.sicuro:
        return f'Ordine NON inviato: {exc}'
    return f'Invio non confermato: {exc} Da {VERIFICA_WEBT}.'


def esegui_job(job_id: int, righe: list) -> None:
    close_old_connections()
    try:
        job = LogistaInvioJob.objects.get(id=job_id)
        url, key = logista_config()
        if not key:
            job.stato = LogistaInvioJob.ERRORE
            job.fase = FASE_CARICAMENTO
            job.errore = 'Servizio Logista non configurato.'
            job.save()
            return
        try:
            data = posta_carica(url, key, righe, job.svuota)
        except LogistaServiceError as exc:
            job.stato = LogistaInvioJob.ERRORE
            job.fase = FASE_CARICAMENTO
            job.errore = str(exc)
            job.save()
            return
        if not applica_risposta(job, data):
            job.save()
            return
        job.stato = LogistaInvioJob.IN_CORSO_INVIO
        job.fase = FASE_INVIO
        job.save()
        # Un solo tentativo: mai ripetere /logista/invia.
        try:
            esito = posta_invia(url, key)
        except LogistaServiceError as exc:
            job.stato = LogistaInvioJob.ERRORE
            job.errore = _errore_invio(exc)
            job.save()
            return
        applica_invio(job, esito)
        job.save()
    except Exception:
        logger.exception('job Logista %s fallito', job_id)
        LogistaInvioJob.objects.filter(id=job_id).update(
            stato=LogistaInvioJob.ERRORE,
            errore=f'Errore interno durante il job Logista: {VERIFICA_WEBT}.',
        )
    finally:
        _notifica_sicura(job_id)
        close_old_connections()


def avvia_job(job: LogistaInvioJob, righe: list) -> threading.Thread:
    thread = threading.Thread(
        target=esegui_job,
        args=(job.id, righe),
        daemon=True,
        name=f'logista-job-{job.id}',
    )
    thread.start()
    return thread


def scadi_job_bloccati(company) -> None:
    """Un riavvio del backend lascia job in corso orfani: li chiude dopo 30 minuti."""
    limite = timezone.now() - JOB_SCADUTO
    orfani = list(LogistaInvioJob.objects.filter(
        company=company, stato__in=STATI_IN_CORSO, creato_il__lt=limite,
    ).values_list('id', 'stato'))
    if not orfani:
        return
    for job_id, stato in orfani:
        if stato == LogistaInvioJob.IN_CORSO_INVIO:
            errore = f'Invio interrotto senza risposta: {VERIFICA_WEBT}.'
        else:
            errore = 'Caricamento interrotto (nessuna risposta dal servizio).'
        LogistaInvioJob.objects.filter(id=job_id, stato=stato).update(stato=LogistaInvioJob.ERRORE, errore=errore)
    for job_id, _stato in orfani:
        threading.Thread(
            target=_notifica_sicura, args=(job_id,), daemon=True, name=f'logista-notifica-{job_id}',
        ).start()


def job_attivo(company):
    return LogistaInvioJob.objects.filter(company=company, stato__in=STATI_IN_CORSO).first()


def crea_job(company, preordine, user, svuota: bool, origine: str):
    """Crea e avvia il job. Ritorna (job, None) oppure (None, (http_status, messaggio, job_attivo_id))."""
    righe = righe_logista_payload(list(preordine.righe.filter(unita__gt=0).order_by('aams')))
    if not righe:
        return None, (409, 'Nessuna riga con quantità da caricare.', None)
    scadi_job_bloccati(company)
    attivo = job_attivo(company)
    if attivo:
        return None, (409, 'C’è già un job Logista in corso.', attivo.id)
    job = LogistaInvioJob.objects.create(
        company=company,
        preordine=preordine,
        creato_da=user,
        origine=origine,
        svuota=bool(svuota),
        righe_inviate=len(righe),
    )
    avvia_job(job, righe)
    return job, None


def job_json(job: LogistaInvioJob) -> dict:
    risultato = job.risultato or {}
    proposta = risultato.get('proposta') or {}
    invio = _invio(job)
    base = f'/api/tabacchi/logista/job/{job.id}/foto/'
    return {
        'id': job.id,
        'stato': job.stato,
        'fase': job.fase,
        'origine': job.origine,
        'svuota': job.svuota,
        'preordine_id': job.preordine_id,
        'righe_inviate': job.righe_inviate,
        'righe_presenti': job.righe_presenti,
        'inserite': risultato.get('inserite'),
        'rifiutate': risultato.get('rifiutate') or [],
        'avvisi': risultato.get('avvisi') or [],
        'proposta': {
            'tabacchi': proposta.get('tabacchi'),
            'altri': proposta.get('altri'),
            'testo': proposta.get('testo') or '',
        },
        'codice_ordine': job.codice_ordine,
        'data_consegna': job.data_consegna_logista,
        'totali': invio.get('totali') or [],
        'conferma': invio.get('conferma') or '',
        'foto_url': base if job.foto_path else None,
        'foto_invio_url': f'{base}?tipo=invio' if job.foto_invio_path else None,
        'errore': job.errore,
        'minuti_stimati': max(1, -(-job.righe_inviate * SECONDI_PER_RIGA // 60)) + 3,
        'creato_il': timezone.localtime(job.creato_il).isoformat(timespec='seconds'),
    }
