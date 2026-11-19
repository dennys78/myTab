"""Client del servizio locale «logista» (Mac mini): carica l'ordine nella proposta WebT.

Il servizio inserisce le righe nella proposta; l'invio finale resta all'utente su WebT.
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
SECONDI_PER_RIGA = 3
JOB_SCADUTO = timedelta(minutes=25)
N8N_TIMEOUT = 20
N8N_TENTATIVI = 2
FAMIGLIE_ALTRI = ('Dispositivi', 'Solidi')
STATI_FINALI = (LogistaInvioJob.COMPLETATO, LogistaInvioJob.ATTESA_CONFERMA, LogistaInvioJob.ERRORE)


class LogistaServiceError(RuntimeError):
    pass


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
        return 'Servizio Logista occupato: un altro caricamento è in corso. Riprova tra qualche minuto.'
    if exc.code in (401, 403):
        return 'Servizio Logista: chiave non valida.'
    return f'Servizio Logista ha risposto {exc.code}' + (f': {dettaglio}' if dettaglio else '.')


def posta_carica(url: str, key: str, righe: list, svuota: bool, timeout: int = CARICA_TIMEOUT) -> dict:
    raw = json.dumps({'righe': righe, 'svuota': bool(svuota)}).encode('utf-8')
    richiesta = urllib.request.Request(
        f'{url}/logista/carica',
        data=raw,
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
        raise LogistaServiceError(_messaggio_http(exc)) from exc
    except urllib.error.URLError as exc:
        raise LogistaServiceError(
            'Servizio Logista non raggiungibile sul Mac mini (porta 3501).'
        ) from exc
    except TimeoutError as exc:
        raise LogistaServiceError('Servizio Logista: tempo scaduto (20 minuti).') from exc
    try:
        data = json.loads(body or '{}')
    except ValueError as exc:
        raise LogistaServiceError('Servizio Logista: risposta non valida.') from exc
    if not isinstance(data, dict):
        raise LogistaServiceError('Servizio Logista: risposta non valida.')
    return data


def _foto_relativa(job_id: int) -> str:
    return f'logista/{job_id}.jpg'


def salva_foto(job_id: int, foto_b64: str) -> str:
    if not foto_b64:
        return ''
    try:
        data = base64.b64decode(foto_b64, validate=False)
    except (ValueError, TypeError):
        return ''
    if not data:
        return ''
    rel = _foto_relativa(job_id)
    path = Path(settings.MEDIA_ROOT) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel


def applica_risposta(job: LogistaInvioJob, data: dict) -> None:
    """Aggiorna il job in base alla risposta di /logista/carica (senza salvare il base64)."""
    if data.get('errore'):
        job.stato = LogistaInvioJob.ERRORE
        job.errore = str(data.get('errore'))[:2000]
        return
    esito = data.get('esito')
    if esito == 'proposta_non_vuota':
        job.stato = LogistaInvioJob.ATTESA_CONFERMA
        try:
            job.righe_presenti = int(data.get('righe_presenti') or 0)
        except (TypeError, ValueError):
            job.righe_presenti = 0
        job.risultato = {'esito': esito, 'righe_presenti': job.righe_presenti}
        return
    if esito == 'caricato':
        foto_b64 = data.get('foto_jpeg_base64') or ''
        risultato = {k: v for k, v in data.items() if k != 'foto_jpeg_base64'}
        job.foto_path = salva_foto(job.id, foto_b64)
        job.risultato = risultato
        job.stato = LogistaInvioJob.COMPLETATO
        job.errore = ''
        return
    job.stato = LogistaInvioJob.ERRORE
    job.errore = f'Servizio Logista: esito non previsto ({esito or "vuoto"}).'


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


def _foto_base64(job: LogistaInvioJob) -> str:
    if not job.foto_path:
        return ''
    path = Path(settings.MEDIA_ROOT) / job.foto_path
    if not path.is_file():
        return ''
    return base64.b64encode(path.read_bytes()).decode('ascii')


def payload_n8n(job: LogistaInvioJob) -> dict:
    risultato = job.risultato or {}
    proposta = risultato.get('proposta') or {}
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
    if job.stato == LogistaInvioJob.ERRORE:
        payload['errore'] = job.errore
    if job.stato == LogistaInvioJob.COMPLETATO:
        payload['foto_jpeg_base64'] = _foto_base64(job)
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


def _notifica_sicura(job_id: int) -> None:
    try:
        job = LogistaInvioJob.objects.select_related('preordine').get(id=job_id)
        notifica_n8n(job)
    except Exception:
        logger.exception('notifica n8n tabacchi job %s non riuscita', job_id)


def esegui_job(job_id: int, righe: list) -> None:
    close_old_connections()
    try:
        job = LogistaInvioJob.objects.get(id=job_id)
        url, key = logista_config()
        if not key:
            job.stato = LogistaInvioJob.ERRORE
            job.errore = 'Servizio Logista non configurato.'
            job.save()
            return
        try:
            data = posta_carica(url, key, righe, job.svuota)
        except LogistaServiceError as exc:
            job.stato = LogistaInvioJob.ERRORE
            job.errore = str(exc)
            job.save()
            return
        applica_risposta(job, data)
        job.save()
    except Exception:
        logger.exception('job Logista %s fallito', job_id)
        LogistaInvioJob.objects.filter(id=job_id).update(
            stato=LogistaInvioJob.ERRORE,
            errore='Errore interno durante il caricamento su Logista.',
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
    """Un riavvio del backend lascia job in_corso orfani: li chiude dopo 25 minuti."""
    orfani = list(LogistaInvioJob.objects.filter(
        company=company,
        stato=LogistaInvioJob.IN_CORSO,
        creato_il__lt=timezone.now() - JOB_SCADUTO,
    ).values_list('id', flat=True))
    if not orfani:
        return
    LogistaInvioJob.objects.filter(id__in=orfani, stato=LogistaInvioJob.IN_CORSO).update(
        stato=LogistaInvioJob.ERRORE,
        errore='Caricamento interrotto (nessuna risposta dal servizio).',
    )
    if not n8n_tabacchi_config()[0]:
        return
    for job_id in orfani:
        threading.Thread(
            target=_notifica_sicura, args=(job_id,), daemon=True, name=f'logista-notifica-{job_id}',
        ).start()


def crea_job(company, preordine, user, svuota: bool, origine: str):
    """Crea e avvia il job. Ritorna (job, None) oppure (None, (http_status, messaggio, job_attivo_id))."""
    righe = righe_logista_payload(list(preordine.righe.filter(unita__gt=0).order_by('aams')))
    if not righe:
        return None, (409, 'Nessuna riga con quantità da caricare.', None)
    scadi_job_bloccati(company)
    attivo = LogistaInvioJob.objects.filter(company=company, stato=LogistaInvioJob.IN_CORSO).first()
    if attivo:
        return None, (409, 'C’è già un caricamento in corso su Logista.', attivo.id)
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
    return {
        'id': job.id,
        'stato': job.stato,
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
        'foto_url': f'/api/tabacchi/logista/job/{job.id}/foto/' if job.foto_path else None,
        'errore': job.errore,
        'minuti_stimati': max(1, -(-job.righe_inviate * SECONDI_PER_RIGA // 60)),
        'creato_il': timezone.localtime(job.creato_il).isoformat(timespec='seconds'),
    }
