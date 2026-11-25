import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Trash2, Wifi } from 'lucide-react';
import { apiFetch } from './api';
import {
  DEFAULT_SCORTA_PCT,
  GIORNI,
  SCORTA_PCT_MAX,
  SCORTA_PCT_MIN,
  SEZIONI_ORDINE,
  altriArticoli,
  conteggiSezioni,
  elencoCopia,
  formattaChiusura,
  formattaResiduo,
  gruppiDaOrdinare,
  isoLocale,
  normalizzaScortaPct,
  prossimoGiornoConsegna,
  ricalcolaRighe,
  righeSezione,
  sezioneDiRiga,
  totaliOrdine,
} from './tabacchiCalc';

function euro(value) {
  if (!Number(value)) return '';
  return `${Number(value).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function mediaTesto(value) {
  return Number(value || 0).toLocaleString('it-IT', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

const STATI_LOGISTA_IN_CORSO = ['in_corso_caricamento', 'in_corso_invio'];
const FAMIGLIE_ALTRI = ['Dispositivi', 'Solidi'];

export default function OrdineTabacchi() {
  const oggi = isoLocale(new Date());
  const [online, setOnline] = useState(null);
  const [preordine, setPreordine] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [deposito, setDeposito] = useState(false);
  const [errore, setErrore] = useState('');
  const [messaggio, setMessaggio] = useState('');
  const [altriAperti, setAltriAperti] = useState(false);
  const [ricerca, setRicerca] = useState('');
  const [copiato, setCopiato] = useState(false);
  const [ordinamento, setOrdinamento] = useState({ chiave: 'residuo', direzione: 'asc' });
  const [sezione, setSezione] = useState('tabacchi');
  const [scortaUltimo, setScortaUltimo] = useState(DEFAULT_SCORTA_PCT);
  const [logistaJob, setLogistaJob] = useState(null);
  const [logistaAvvio, setLogistaAvvio] = useState(false);
  const [manualeQuery, setManualeQuery] = useState('');
  const [manualeUnita, setManualeUnita] = useState(1);
  const [manualeRisultati, setManualeRisultati] = useState([]);
  const [manualeScelto, setManualeScelto] = useState(null);
  const [manualeAttesa, setManualeAttesa] = useState(false);
  const pollRef = useRef(null);
  const saveRef = useRef(null);
  const salvaPendenteRef = useRef(null);
  const logistaPollRef = useRef(null);
  const seguiJobLogistaRef = useRef(null);
  const copiaRef = useRef(null);
  const manualeTimerRef = useRef(null);

  const ferma = () => {
    if (pollRef.current) clearTimeout(pollRef.current);
    if (saveRef.current) clearTimeout(saveRef.current);
    if (logistaPollRef.current) clearTimeout(logistaPollRef.current);
    if (manualeTimerRef.current) clearTimeout(manualeTimerRef.current);
  };

  useEffect(() => () => ferma(), []);

  const resetManuale = () => {
    setManualeQuery('');
    setManualeUnita(1);
    setManualeRisultati([]);
    setManualeScelto(null);
  };

  const cercaManuale = useCallback((testo, preordineId) => {
    if (manualeTimerRef.current) clearTimeout(manualeTimerRef.current);
    const q = String(testo || '').trim();
    if (!preordineId || q.length < 1) {
      setManualeRisultati([]);
      return;
    }
    manualeTimerRef.current = setTimeout(async () => {
      try {
        const response = await apiFetch(
          `/api/tabacchi/preordini/${preordineId}/anagrafica/?q=${encodeURIComponent(q)}&limit=12`,
        );
        const data = await response.json();
        if (data.status !== 'success') {
          setManualeRisultati([]);
          return;
        }
        setManualeRisultati(data.risultati || []);
      } catch {
        setManualeRisultati([]);
      }
    }, 220);
  }, []);

  const aggiungiManuale = async () => {
    if (!preordine?.modificabile || !manualeScelto?.aams) return;
    const unita = Math.max(1, Number.parseInt(manualeUnita, 10) || 1);
    setManualeAttesa(true);
    setErrore('');
    setMessaggio('');
    try {
      const response = await apiFetch(`/api/tabacchi/preordini/${preordine.id}/righe/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ aams: manualeScelto.aams, unita }),
      });
      const data = await response.json();
      if (data.status !== 'success') {
        setErrore(data.error || 'Impossibile aggiungere l\'articolo.');
        return;
      }
      setPreordine(data.preordine);
      setMessaggio(`Aggiunto ${manualeScelto.descrizione || manualeScelto.aams} · ${unita}`);
      resetManuale();
      const nuovaSezione = sezioneDiRiga(
        data.preordine.righe.find(riga => riga.aams === manualeScelto.aams) || manualeScelto,
      );
      if (nuovaSezione) setSezione(nuovaSezione);
    } catch {
      setErrore('Impossibile aggiungere l\'articolo.');
    } finally {
      setManualeAttesa(false);
    }
  };

  const caricaStato = useCallback(() => {
    apiFetch('/api/tabauno/status/')
      .then(r => r.json())
      .then(d => { if (d.status === 'success') setOnline(!!d.agent_online); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    caricaStato();
    const timer = setInterval(caricaStato, 5000);
    return () => clearInterval(timer);
  }, [caricaStato]);

  const apri = useCallback(async (id) => {
    const response = await apiFetch(`/api/tabacchi/preordini/${id}/`);
    const data = await response.json();
    if (data.status === 'success') {
      setPreordine(data.preordine);
      setScortaUltimo(normalizzaScortaPct(data.preordine.scorta_pct));
      setOnline(data.preordine.agent_online);
      const job = data.preordine.logista_job;
      if (job && (STATI_LOGISTA_IN_CORSO.includes(job.stato) || job.stato === 'attesa_conferma')) {
        setLogistaJob(job);
        if (STATI_LOGISTA_IN_CORSO.includes(job.stato)) seguiJobLogistaRef.current?.(job.id);
      }
    }
  }, []);

  useEffect(() => {
    apiFetch('/api/tabacchi/preordini/')
      .then(r => r.json())
      .then(d => {
        if (d.status !== 'success') return;
        setOnline(!!d.agent_online);
        if (d.scorta_ultimo != null) setScortaUltimo(normalizzaScortaPct(d.scorta_ultimo));
        else if (d.preordini?.[0]?.scorta_pct != null) {
          setScortaUltimo(normalizzaScortaPct(d.preordini[0].scorta_pct));
        }
        const bozza = (d.preordini || []).find(row => row.stato === 'bozza' || row.stato === 'esportato');
        if (bozza) apri(bozza.id);
      })
      .catch(() => {});
  }, [apri]);

  const salva = useCallback((next, righePatch) => {
    if (saveRef.current) clearTimeout(saveRef.current);
    const esegui = async () => {
      saveRef.current = null;
      salvaPendenteRef.current = null;
      const response = await apiFetch(`/api/tabacchi/preordini/${next.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          giorni_copertura: next.giorni_copertura,
          scorta_pct: next.scorta_pct,
          data_consegna: next.data_consegna,
          righe: righePatch || next.righe.map(riga => ({ aams: riga.aams, unita: riga.unita })),
        }),
      });
      const data = await response.json();
      if (data.status === 'success') setPreordine(data.preordine);
      else setErrore(data.error || 'Salvataggio non riuscito.');
    };
    salvaPendenteRef.current = esegui;
    saveRef.current = setTimeout(esegui, 350);
  }, []);

  const salvaSubito = async () => {
    const pendente = salvaPendenteRef.current;
    if (!pendente) return;
    if (saveRef.current) clearTimeout(saveRef.current);
    await pendente();
  };

  const aggiornaParametri = (patch) => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const giorni = patch.giorni_copertura ?? prev.giorni_copertura;
      const consegna = patch.data_consegna ?? prev.data_consegna;
      const scortaPct = normalizzaScortaPct(patch.scorta_pct ?? prev.scorta_pct ?? scortaUltimo);
      const righe = ricalcolaRighe(prev.righe, {
        giorniCopertura: giorni,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: consegna,
        scortaPct,
      });
      const totali = totaliOrdine(righe);
      setScortaUltimo(scortaPct);
      const next = {
        ...prev,
        giorni_copertura: giorni,
        scorta_pct: scortaPct,
        data_consegna: consegna,
        giorni_alla_consegna: righe[0]?.giorni_alla_consegna ?? prev.giorni_alla_consegna,
        righe,
        articoli: totali.articoli,
        stecche: totali.stecche,
        kg: totali.kg,
        totale: totali.importo,
      };
      salva(next);
      return next;
    });
  };

  const impostaUnita = (aams, unita) => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const toccate = prev.righe.map(riga => (
        riga.aams === aams
          ? { ...riga, unita: Math.max(0, Number(unita)), corretto_a_mano: true }
          : riga
      ));
      const righe = ricalcolaRighe(toccate, {
        giorniCopertura: prev.giorni_copertura,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: prev.data_consegna,
        scortaPct: prev.scorta_pct,
      });
      const totali = totaliOrdine(righe);
      const next = {
        ...prev,
        righe,
        articoli: totali.articoli,
        stecche: totali.stecche,
        kg: totali.kg,
        totale: totali.importo,
      };
      salva(next, [{ aams, unita: righe.find(riga => riga.aams === aams).unita }]);
      return next;
    });
  };

  const cambiaUnita = (aams, delta) => {
    const attuale = preordine?.righe?.find(riga => riga.aams === aams);
    if (!attuale || !preordine?.modificabile) return;
    impostaUnita(aams, Math.max(0, Number(attuale.unita) + delta));
  };

  const rimuoviDaOrdine = (riga) => {
    if (!preordine?.modificabile || Number(riga.unita) <= 0) return;
    const ok = window.confirm(
      `Togliere «${riga.descrizione}» dall'ordine?\nLa quantità verrà messa a zero.`,
    );
    if (!ok) return;
    impostaUnita(riga.aams, 0);
  };

  const annullaCorrezioni = () => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const pulite = prev.righe.map(riga => ({
        ...riga,
        corretto_a_mano: false,
        unita: riga.unita_proposte,
      }));
      const righe = ricalcolaRighe(pulite, {
        giorniCopertura: prev.giorni_copertura,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: prev.data_consegna,
        scortaPct: prev.scorta_pct,
      });
      const totali = totaliOrdine(righe);
      const next = {
        ...prev,
        righe,
        articoli: totali.articoli,
        stecche: totali.stecche,
        kg: totali.kg,
        totale: totali.importo,
      };
      salva(next);
      return next;
    });
  };

  const leggi = async () => {
    setErrore('');
    setAttesa(true);
    const response = await apiFetch('/api/tabacchi/preordini/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const data = await response.json();
    if (data.status !== 'success') {
      setAttesa(false);
      setErrore(data.error || 'Richiesta non accodata.');
      return;
    }
    setOnline(data.agent_online);
    const poll = async () => {
      const stato = await apiFetch(`/api/tabauno/requests/${data.id}/`);
      const body = await stato.json();
      setOnline(!!body.agent_online);
      if (body.status === 'done') {
        const consegna = prossimoGiornoConsegna(oggi);
        const creato = await apiFetch(`/api/tabacchi/preordini/da-richiesta/${data.id}/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            giorni_copertura: 7,
            scorta_pct: normalizzaScortaPct(scortaUltimo),
            data_consegna: consegna,
          }),
        });
        const ordine = await creato.json();
        setAttesa(false);
        if (ordine.status === 'success') {
          setPreordine(ordine.preordine);
          setScortaUltimo(normalizzaScortaPct(ordine.preordine.scorta_pct));
        } else setErrore(ordine.error || 'Calcolo non riuscito.');
        return;
      }
      if (body.status === 'error' || body.status === 'expired') {
        setAttesa(false);
        setErrore(body.error || 'Lettura TabaUno non riuscita.');
        return;
      }
      pollRef.current = setTimeout(poll, 2000);
    };
    pollRef.current = setTimeout(poll, 2000);
  };

  const elimina = async ({ poiLeggi = false } = {}) => {
    if (!preordine) return;
    const messaggio = poiLeggi
      ? 'Eliminare questo ordine e fare una nuova lettura da PC?'
      : 'Eliminare definitivamente questo ordine?';
    if (!window.confirm(messaggio)) return;
    const response = await apiFetch(`/api/tabacchi/preordini/${preordine.id}/`, { method: 'DELETE' });
    const data = await response.json();
    if (data.status !== 'success') {
      setErrore(data.error || 'Eliminazione non riuscita.');
      return;
    }
    setPreordine(null);
    setAltriAperti(false);
    setRicerca('');
    if (poiLeggi) await leggi();
  };

  const scaricaLogista = () => {
    if (!preordine) return;
    window.location.assign(`/api/tabacchi/preordini/${preordine.id}/logista/`);
  };

  const depositaInTabauno = async () => {
    if (!preordine || deposito) return;
    setErrore('');
    setMessaggio('');
    if (online !== true) {
      setErrore('PC negozio offline. Avvia TabaUnoAgent e riprova.');
      return;
    }
    const conQuantita = (preordine.righe || []).some(riga => Number(riga.unita) > 0);
    if (!conQuantita) {
      setErrore('Nessuna riga con quantità da depositare.');
      return;
    }
    setDeposito(true);
    const response = await apiFetch(`/api/tabacchi/preordini/${preordine.id}/deposita-tabauno/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const data = await response.json();
    if (data.status !== 'success') {
      setDeposito(false);
      setOnline(data.agent_online === undefined ? online : !!data.agent_online);
      setErrore(data.error || 'Deposito non accodato.');
      return;
    }
    setOnline(!!data.agent_online);
    const poll = async () => {
      const stato = await apiFetch(`/api/tabauno/requests/${data.id}/`);
      const body = await stato.json();
      setOnline(!!body.agent_online);
      if (body.status === 'done') {
        setDeposito(false);
        const payload = body.payload || {};
        const path = String(payload.path || '').trim();
        const size = Number(payload.bytes || 0);
        if (!path || size <= 0) {
          setErrore('Il PC remoto non ha confermato la generazione del file Ordine_Logista.xls.');
          return;
        }
        const dettaglio = payload.messaggio
          || `Ordine_Logista.xls generato correttamente sul PC remoto in ${path} (${size.toLocaleString('it-IT')} byte).`;
        setMessaggio(dettaglio);
        setPreordine(prev => (prev ? { ...prev, stato: 'esportato', modificabile: true } : prev));
        return;
      }
      if (body.status === 'error' || body.status === 'expired') {
        setDeposito(false);
        setErrore(body.error || 'Deposito su TabaUno non riuscito sul PC remoto.');
        return;
      }
      pollRef.current = setTimeout(poll, 2000);
    };
    pollRef.current = setTimeout(poll, 2000);
  };

  const seguiJobLogista = (jobId) => {
    if (logistaPollRef.current) clearTimeout(logistaPollRef.current);
    const poll = async () => {
      try {
        const response = await apiFetch(`/api/tabacchi/logista/job/${jobId}/`);
        const data = await response.json();
        if (data.status === 'success') {
          setLogistaJob(data.job);
          if (!STATI_LOGISTA_IN_CORSO.includes(data.job.stato)) return;
        }
      } catch {
        // rete instabile: si riprova al giro successivo
      }
      logistaPollRef.current = setTimeout(poll, 3000);
    };
    logistaPollRef.current = setTimeout(poll, 3000);
  };
  seguiJobLogistaRef.current = seguiJobLogista;

  const avviaLogista = async (svuota) => {
    if (!preordine || logistaAvvio) return;
    setErrore('');
    setMessaggio('');
    setLogistaAvvio(true);
    try {
      await salvaSubito();
      const response = await apiFetch('/api/tabacchi/logista/invia/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ preordine_id: preordine.id, svuota }),
      });
      const data = await response.json();
      if (data.status !== 'success') {
        if (data.job_id) {
          setLogistaJob({ id: data.job_id, stato: 'in_corso_caricamento', righe_inviate: 0, minuti_stimati: 1 });
          seguiJobLogista(data.job_id);
        } else {
          setLogistaJob({ stato: 'errore', fase: 'caricamento', errore: data.error || 'Invio a Logista non riuscito.' });
        }
        return;
      }
      setLogistaJob(data.job);
      seguiJobLogista(data.job_id);
    } catch {
      setLogistaJob({ stato: 'errore', fase: 'caricamento', errore: 'Impossibile contattare il server myTaba.' });
    } finally {
      setLogistaAvvio(false);
    }
  };

  const inviaALogista = () => {
    if (!preordine) return;
    if (!preordine.logista_configurato) {
      setLogistaJob({ stato: 'errore', fase: 'caricamento', errore: 'Servizio Logista non configurato.' });
      return;
    }
    const attive = (preordine.righe || []).filter(riga => Number(riga.unita) > 0);
    if (!attive.length) {
      setErrore('Nessuna riga con quantità da caricare.');
      return;
    }
    const pezziAltri = attive
      .filter(riga => FAMIGLIE_ALTRI.includes(riga.famiglia))
      .reduce((somma, riga) => somma + Number(riga.unita || 0), 0);
    const kg = Number(preordine.kg || 0).toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 });
    const testo = `Verranno caricate ${attive.length} righe (${kg} kg tabacco, ${pezziAltri} pz altri) `
      + 'e l\'ordine verrà INVIATO a Logista in modo definitivo. Procedere?';
    if (!window.confirm(testo)) return;
    avviaLogista(false);
  };

  const logistaInCorso = logistaAvvio || STATI_LOGISTA_IN_CORSO.includes(logistaJob?.stato);

  const fotoLogista = (url, alt) => (url ? (
    <a href={url} target="_blank" rel="noreferrer" className="tab-logista-foto">
      <img src={url} alt={alt} />
    </a>
  ) : null);

  const elencoRifiutate = (job) => {
    const rifiutate = job.rifiutate || [];
    if (!rifiutate.length) return null;
    return (
      <div className="tab-logista-rifiutate">
        <strong>Rifiutate ({rifiutate.length})</strong>
        <ul>
          {rifiutate.map((riga, i) => (
            <li key={`${riga.codice}-${i}`}>
              <span className="tab-aams">{riga.codice}</span> {riga.qta} — {riga.errore}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const elencoAvvisi = (job) => {
    const avvisi = job.avvisi || [];
    if (!avvisi.length) return null;
    return (
      <div className="tab-logista-avvisi">
        <strong>Avvisi</strong>
        <ul>
          {avvisi.map((riga, i) => (
            <li key={`${riga.codice}-${i}`}>
              <span className="tab-aams">{riga.codice}</span> {(riga.avvisi || []).join(' · ')}
            </li>
          ))}
        </ul>
      </div>
    );
  };

  const chiudiLogista = (
    <button type="button" className="tab-btn ghost" onClick={() => setLogistaJob(null)}>Chiudi</button>
  );

  const pannelloLogista = () => {
    if (!logistaJob) return null;
    const job = logistaJob;
    if (STATI_LOGISTA_IN_CORSO.includes(job.stato)) {
      return (
        <div className="tab-logista">
          {job.stato === 'in_corso_invio'
            ? 'Invio ordine a Logista… (fino a 3 minuti)'
            : `Caricamento righe… (~${job.minuti_stimati || 1} minuti in tutto)`}
        </div>
      );
    }
    if (job.stato === 'attesa_conferma') {
      return (
        <div className="tab-logista warn">
          <p>Su WebT c&apos;è già una proposta con {job.righe_presenti ?? 0} righe. Svuotarla, caricare e inviare questo ordine?</p>
          <div className="tab-logista-actions">
            <button type="button" className="tab-btn primary" onClick={() => avviaLogista(true)} disabled={logistaInCorso}>
              Svuota, carica e invia
            </button>
            <button type="button" className="tab-btn ghost" onClick={() => setLogistaJob(null)}>
              Annulla
            </button>
          </div>
        </div>
      );
    }
    if (job.stato === 'inviato') {
      return (
        <div className="tab-logista ok">
          <div className="tab-logista-head">
            <div>
              <strong>✅ Ordine INVIATO a Logista</strong>
              <span className="tab-logista-conteggi">
                Codice ordine <strong>{job.codice_ordine || '—'}</strong> · Consegna <strong>{job.data_consegna || '—'}</strong>
              </span>
              {(job.kg_tabacco || job.pezzi_elettronici) && (
                <span className="tab-logista-conteggi">
                  Tabacco {job.kg_tabacco || '—'} kg · Altri prodotti {job.pezzi_elettronici || '0'} pz
                </span>
              )}
              {job.totale_importo ? (
                <span className="tab-logista-conteggi">Importo <strong>{job.totale_importo}</strong></span>
              ) : (job.totali || []).map((riga, i) => (
                <span key={i} className="tab-logista-conteggi">{riga}</span>
              ))}
              <span className="tab-logista-conteggi">Righe inserite {job.inserite ?? 0}/{job.righe_inviate}</span>
            </div>
            {fotoLogista(job.foto_invio_url || job.foto_url, 'Conferma invio su WebT')}
          </div>
          {elencoRifiutate(job)}
          {elencoAvvisi(job)}
          <div className="tab-logista-actions">{chiudiLogista}</div>
        </div>
      );
    }
    if (job.stato === 'incerto') {
      return (
        <div className="tab-logista warn">
          <div className="tab-logista-head">
            <div>
              <p className="tab-logista-nota">
                {job.avviso_incerto || "❓ Esito invio non confermato. L'ordine potrebbe essere già partito: NON reinviare, controlla su WebT (Report → ordini)."}
              </p>
              {job.errore && <p>{job.errore}</p>}
            </div>
            {fotoLogista(job.foto_invio_url || job.foto_url, 'Stato WebT')}
          </div>
          {elencoRifiutate(job)}
          <div className="tab-logista-actions">{chiudiLogista}</div>
        </div>
      );
    }
    const nienteCaricato = job.fase === 'caricamento' && !job.inserite;
    return (
      <div className={`tab-logista ${job.stato === 'errore' ? 'error' : 'warn'}`}>
        <div className="tab-logista-head">
          <div>
            <strong>⚠️ Ordine NON inviato</strong>
            {job.fase && <span className="tab-logista-conteggi">Fase: {job.fase}</span>}
            <p>{job.errore || 'Operazione su Logista non riuscita.'}</p>
            {!nienteCaricato && (
              <p className="tab-logista-nota">La proposta caricata è rimasta su WebT: controlla e invia a mano.</p>
            )}
          </div>
          {fotoLogista(job.foto_invio_url || job.foto_url, 'Stato WebT')}
        </div>
        {elencoRifiutate(job)}
        <div className="tab-logista-actions">
          {nienteCaricato && job.stato === 'errore' && preordine?.logista_configurato && (
            <button type="button" className="tab-btn ghost" onClick={() => avviaLogista(false)} disabled={logistaInCorso}>
              Riprova
            </button>
          )}
          {chiudiLogista}
        </div>
      </div>
    );
  };

  const copiaElenco = async () => {
    if (!preordine) return;
    const testo = elencoCopia(preordine.righe);
    try {
      await navigator.clipboard.writeText(testo);
      setCopiato(true);
      setTimeout(() => setCopiato(false), 1600);
    } catch {
      if (copiaRef.current) {
        copiaRef.current.value = testo;
        copiaRef.current.focus();
        copiaRef.current.select();
      }
    }
  };

  const impostaOrdinamento = (chiave) => {
    setOrdinamento(prev => {
      if (prev.chiave === chiave) {
        return { chiave, direzione: prev.direzione === 'asc' ? 'desc' : 'asc' };
      }
      return { chiave, direzione: chiave === 'importo' ? 'desc' : 'asc' };
    });
  };

  const etichettaSort = (chiave, label) => {
    const attivo = ordinamento.chiave === chiave;
    const freccia = !attivo ? '' : ordinamento.direzione === 'asc' ? ' ↑' : ' ↓';
    return (
      <button
        type="button"
        className={`tab-sort${attivo ? ' active' : ''}`}
        onClick={() => impostaOrdinamento(chiave)}
        aria-label={`Ordina per ${label}`}
      >
        {label}{freccia}
      </button>
    );
  };

  const conteggi = useMemo(
    () => (preordine ? conteggiSezioni(preordine.righe) : null),
    [preordine],
  );
  const gruppi = useMemo(
    () => (preordine ? gruppiDaOrdinare(preordine.righe, { ...ordinamento, sezioneId: sezione }) : []),
    [preordine, ordinamento, sezione],
  );
  const altri = useMemo(() => {
    const base = preordine ? altriArticoli(preordine.righe, ordinamento) : [];
    const rows = base.filter(riga => sezioneDiRiga(riga) === sezione);
    const q = ricerca.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter(riga => (
      String(riga.descrizione).toLowerCase().includes(q)
      || String(riga.aams).toLowerCase().includes(q)
    ));
  }, [preordine, ricerca, ordinamento, sezione]);
  const altriTotaliSezione = preordine
    ? altriArticoli(preordine.righe).filter(riga => sezioneDiRiga(riga) === sezione).length
    : 0;
  const haCorrezioni = !!preordine?.righe?.some(riga => riga.corretto_a_mano);
  const unitaLabel = sezione === 'tabacchi' ? 'Stecche' : 'Conf.';
  const sezioneMeta = conteggi?.[sezione];
  const senzaLetturaDsp = preordine
    && righeSezione(preordine.righe, 'dispositivi').length === 0
    && righeSezione(preordine.righe, 'solidi').length === 0;

  const giorniCopertura = preordine?.giorni_copertura || 7;
  const cellaResiduo = (riga) => {
    const urgenza = riga.urgenza_copertura || 'normale';
    const testo = formattaResiduo(riga.residuo_copertura);
    const title = [
      `Pacchetti stimati al prossimo ordine (dopo ${giorniCopertura} gg di vendita, incluso questo ordine)`,
      riga.giacenza_dopo_consegna != null
        ? `Alla consegna ~${Number(riga.giacenza_dopo_consegna).toLocaleString('it-IT')} pz`
        : null,
      Number(riga.residuo_copertura) < 0
        ? 'Negativo = non bastano fino al prossimo ordine'
        : null,
    ].filter(Boolean).join(' · ');
    return (
      <span className={`tab-residuo tab-finisce--${urgenza}`} title={title}>
        {testo}
      </span>
    );
  };

  const rigaTabella = (riga, { conStepper = true } = {}) => (
    <tr key={riga.aams} className={`gia-row${Number(riga.unita) > 0 ? ' tab-row-order' : ''}`}>
      <td className="gia-col-articolo" title={`${riga.aams} · ${riga.descrizione}`}>
        <span className="gia-nome">{riga.descrizione || '—'}</span>
        <span className="grt-meta">
          {riga.aams}
          {riga.corretto_a_mano ? ' · corretto' : ''}
        </span>
        <div className="tab-mobile-meta">
          <span>{Number(riga.giacenza).toLocaleString('it-IT')}</span>
          <span>·</span>
          <span>{mediaTesto(riga.media)}</span>
          <span>·</span>
          {cellaResiduo(riga)}
        </div>
      </td>
      <td className="gia-col-num tab-desktop-only">{Number(riga.giacenza).toLocaleString('it-IT')}</td>
      <td className="gia-col-num tab-desktop-only">{mediaTesto(riga.media)}</td>
      <td className="gia-col-num tab-desktop-only">
        {cellaResiduo(riga)}
      </td>
      <td className="gia-col-num tab-stecche">
        {conStepper ? (
          <div className="grt-step" role="group" aria-label={`Quantità ${riga.descrizione || riga.aams}`}>
            <button
              type="button"
              className="grt-step-btn"
              onClick={() => cambiaUnita(riga.aams, -1)}
              disabled={!preordine?.modificabile || Number(riga.unita) <= 0}
              aria-label="Diminuisci"
            >
              −
            </button>
            <b className={riga.corretto_a_mano ? 'tab-step-manual' : (Number(riga.unita) > 0 ? 'tab-step-on' : '')}>
              {Number(riga.unita) || 0}
            </b>
            <button
              type="button"
              className="grt-step-btn"
              onClick={() => cambiaUnita(riga.aams, 1)}
              disabled={!preordine?.modificabile}
              aria-label="Aumenta"
            >
              +
            </button>
            {Number(riga.unita) > 0 && (
              <button
                type="button"
                className="tab-trash"
                onClick={() => rimuoviDaOrdine(riga)}
                disabled={!preordine?.modificabile}
                aria-label={`Togli ${riga.descrizione} dall'ordine`}
                title="Togli dall'ordine"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ) : (
          <button
            type="button"
            className="grt-step-btn tab-add"
            onClick={() => cambiaUnita(riga.aams, 1)}
            disabled={!preordine?.modificabile}
            aria-label="Aggiungi"
          >
            +
          </button>
        )}
      </td>
      <td className="gia-col-num tab-importo">{euro(riga.importo)}</td>
    </tr>
  );

  const bottoneLettura = (
    <button
      type="button"
      className="tab-btn primary gia-btn-leggi"
      onClick={() => (preordine ? elimina({ poiLeggi: true }) : leggi())}
      disabled={attesa || (!preordine && online !== true)}
      title={online === true ? 'PC remoto raggiungibile' : 'PC remoto non raggiungibile'}
    >
      <Wifi size={16} aria-hidden="true" />
      {attesa ? 'Lettura…' : preordine ? 'Aggiorna da PC' : 'Leggi da PC'}
    </button>
  );

  return (
    <div className="tab-page tabacchi-page">
      <header className="tab-header">
        <div>
          <h1>Ordine Tabacchi</h1>
          <p className="tab-sub">
            {preordine?.ultimo_giorno_chiuso
              ? `Dati TabaUno alla chiusura del ${formattaChiusura(preordine.ultimo_giorno_chiuso)} · vendite delle ultime 4 settimane`
              : 'Dati TabaUno · vendite delle ultime 4 settimane'}
          </p>
        </div>
      </header>

      {errore && <div className="tab-error">{errore}</div>}
      {messaggio && !errore && <div className="tab-ok">{messaggio}</div>}
      {preordine && pannelloLogista()}

      <div className="tab-controls gia-controls">
        {preordine && (
          <>
            <div className="tab-control">
              <span className="tab-label">Copertura</span>
              <div className="grt-days" role="group" aria-label="Giorni di copertura">
                {GIORNI.map(giorni => (
                  <button
                    key={giorni}
                    type="button"
                    className={`grt-day-btn ${preordine.giorni_copertura === giorni ? 'active' : ''}`}
                    disabled={!preordine.modificabile}
                    onClick={() => aggiornaParametri({ giorni_copertura: giorni })}
                  >
                    {giorni}
                  </button>
                ))}
              </div>
            </div>
            <div className="tab-control">
              <span className="tab-label">Consegna</span>
              <input
                type="date"
                value={preordine.data_consegna}
                disabled={!preordine.modificabile}
                onChange={e => aggiornaParametri({ data_consegna: e.target.value })}
              />
            </div>
            <div className="tab-control tab-control-scorta">
              <span className="tab-label">Scorta {normalizzaScortaPct(preordine.scorta_pct)}%</span>
              <input
                type="range"
                min={SCORTA_PCT_MIN}
                max={SCORTA_PCT_MAX}
                step={5}
                value={normalizzaScortaPct(preordine.scorta_pct)}
                disabled={!preordine.modificabile}
                onChange={e => aggiornaParametri({ scorta_pct: Number(e.target.value) })}
                aria-label="Percentuale di scorta desiderata"
              />
              <div className="tab-scorta-scale">
                <span>{SCORTA_PCT_MIN}%</span>
                <span>200%</span>
                <span>{SCORTA_PCT_MAX}%</span>
              </div>
            </div>
          </>
        )}
        {!preordine && (
          <div className="tab-control gia-control-leggi">
            {bottoneLettura}
          </div>
        )}
      </div>

      {preordine && (
        <div className="tab-controls gia-controls gia-controls-tools">
          <div className="tab-control gia-control-filtri">
            <div className="gia-filtri" role="tablist" aria-label="Tipo merce">
              {SEZIONI_ORDINE.map(item => {
                const stats = conteggi?.[item.id];
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={sezione === item.id}
                    className={`gia-filtro-btn tab-filtro-${item.id} ${sezione === item.id ? 'active' : ''}`}
                    onClick={() => { setSezione(item.id); setAltriAperti(false); setRicerca(''); }}
                  >
                    <span className="gia-filtro-dot" aria-hidden="true" />
                    <span className="gia-filtro-label">{item.label}</span>
                    <span className="gia-filtro-count">{stats?.articoli ?? 0}</span>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="tab-control gia-control-leggi">
            {bottoneLettura}
          </div>
        </div>
      )}

      {!preordine && !attesa && (
        <p className="tab-empty">
          {online === true
            ? 'Premi «Leggi da PC» quando il servizio TabaUnoAgent è online.'
            : 'Il PC remoto non è raggiungibile: avvia TabaUnoAgent e riprova.'}
        </p>
      )}

      {preordine && (
        <>
          <div className="gia-sep" aria-hidden="true" />

          {senzaLetturaDsp && (sezione === 'dispositivi' || sezione === 'solidi') && (
            <p className="tab-empty tab-empty-warn">
              In questa lettura non ci sono {sezione}. Aggiorna l’agente sul PC negozio (file tabacchi.py), riavvia TabaUnoAgent e fai «Nuova lettura».
            </p>
          )}

          <div className="tab-section-head">
            <h2>Da ordinare · {SEZIONI_ORDINE.find(item => item.id === sezione)?.label}</h2>
            {sezioneMeta && (
              <span className="tab-section-meta">
                {sezione === 'tabacchi'
                  ? `${sezioneMeta.kg.toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 })} kg`
                  : `${sezioneMeta.stecche} conf. · ${sezioneMeta.pezzi} pz`}
                {' · '}
                {euro(sezioneMeta.importo) || '0,00 €'}
              </span>
            )}
          </div>

          {gruppi.length === 0 ? (
            <p className="tab-empty">
              {senzaLetturaDsp && sezione !== 'tabacchi'
                ? 'Nessun articolo in questa sezione per la lettura attuale.'
                : 'Niente da ordinare con questa copertura.'}
            </p>
          ) : (
            gruppi.map(group => (
              <div key={group.famiglia} className="tab-family">
                <div className="tab-family-title">
                  <strong>{group.famiglia}</strong>
                  <span>{group.items.length} articoli · subtotale {euro(group.subtotale) || '0,00 €'}</span>
                </div>
                <div className="tab-table-wrap gia-table-wrap">
                  <table className="tab-table gia-table">
                    <thead>
                      <tr>
                        <th className="gia-col-articolo">{etichettaSort('descrizione', 'Articolo')}</th>
                        <th className="gia-col-num">Giac.</th>
                        <th className="gia-col-num">Vende/gg</th>
                        <th className="gia-col-num" title={`Pacchetti che ti restano al prossimo ordine (dopo ${giorniCopertura} gg di vendita, incluso questo ordine)`}>
                          {etichettaSort('residuo', 'Al prox. ordine')}
                        </th>
                        <th className="gia-col-num">{unitaLabel}</th>
                        <th className="gia-col-num">{etichettaSort('importo', 'Importo')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {group.items.map(riga => rigaTabella(riga))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
          )}

          {preordine.modificabile && (
            <section className="tab-manuale">
              <div className="tab-manuale-head">
                <strong>Aggiungi articolo fuori statistica</strong>
                <span>Cerca in anagrafica per codice AAMS o descrizione · giacenza e vendite a zero</span>
              </div>
              <div className="tab-controls gia-controls gia-controls-tools tab-manuale-row">
                <div className="tab-control tab-manuale-cerca">
                  <input
                    type="search"
                    className="tab-search"
                    placeholder="Codice AAMS o descrizione…"
                    value={manualeQuery}
                    disabled={manualeAttesa}
                    onChange={e => {
                      const value = e.target.value;
                      setManualeQuery(value);
                      setManualeScelto(null);
                      cercaManuale(value, preordine.id);
                    }}
                  />
                  {manualeRisultati.length > 0 && !manualeScelto && (
                    <ul className="tab-manuale-suggest" role="listbox">
                      {manualeRisultati.map(item => (
                        <li key={item.aams}>
                          <button
                            type="button"
                            onClick={() => {
                              setManualeScelto(item);
                              setManualeQuery(`${item.aams} · ${item.descrizione}`);
                              setManualeRisultati([]);
                            }}
                          >
                            <strong>{item.descrizione}</strong>
                            <span className="grt-meta">{item.aams} · {item.famiglia}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="tab-control">
                  <span className="tab-label">Q.tà</span>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={manualeUnita}
                    disabled={manualeAttesa}
                    onChange={e => setManualeUnita(Math.max(1, Number.parseInt(e.target.value, 10) || 1))}
                    aria-label="Quantità da aggiungere"
                  />
                </div>
                <div className="tab-control gia-control-leggi">
                  <button
                    type="button"
                    className="tab-btn primary"
                    disabled={manualeAttesa || !manualeScelto}
                    onClick={aggiungiManuale}
                  >
                    {manualeAttesa ? 'Aggiungo…' : 'Aggiungi'}
                  </button>
                </div>
              </div>
            </section>
          )}

          <section className="tab-others">
            <button type="button" className="tab-others-toggle" onClick={() => setAltriAperti(v => !v)}>
              {altriAperti ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span>Altri articoli · {SEZIONI_ORDINE.find(item => item.id === sezione)?.label}</span>
              <em>{altriTotaliSezione} con scorta sufficiente · prima chi arriva al prossimo ordine con meno pz</em>
            </button>
            {altriAperti && (
              <div className="tab-others-body">
                <input
                  type="search"
                  className="tab-search"
                  placeholder="Cerca per nome o codice"
                  value={ricerca}
                  onChange={e => setRicerca(e.target.value)}
                />
                <div className="tab-table-wrap gia-table-wrap">
                  <table className="tab-table gia-table">
                    <thead>
                      <tr>
                        <th className="gia-col-articolo">{etichettaSort('descrizione', 'Articolo')}</th>
                        <th className="gia-col-num">Giac.</th>
                        <th className="gia-col-num">Vende/gg</th>
                        <th className="gia-col-num" title={`Pacchetti che ti restano al prossimo ordine (dopo ${giorniCopertura} gg di vendita, incluso questo ordine)`}>
                          {etichettaSort('residuo', 'Al prox. ordine')}
                        </th>
                        <th className="gia-col-num" />
                        <th className="gia-col-num">{etichettaSort('importo', 'Importo')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {altri.map(riga => rigaTabella(riga, { conStepper: false }))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </section>

          <div className="tab-dock gratta-dock">
            <div className="tab-dock-totals">
              <span>Articoli <strong>{preordine.articoli}</strong></span>
              <span>Stecche/conf. <strong>{preordine.stecche}</strong></span>
              {sezione === 'tabacchi' ? (
                <span>Kg <strong>{Number(preordine.kg || 0).toLocaleString('it-IT', { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</strong></span>
              ) : (
                <span>Pz sezione <strong>{sezioneMeta?.pezzi ?? 0}</strong></span>
              )}
              <span className="tab-dock-total">Totale <strong>{Number(preordine.totale || 0).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €</strong></span>
            </div>
            <div className="tab-dock-actions gratta-dock-actions">
              {haCorrezioni && (
                <button type="button" onClick={annullaCorrezioni}>
                  Annulla correzioni
                </button>
              )}
              <button type="button" className="is-danger" onClick={() => elimina()} disabled={attesa}>
                Elimina
              </button>
              <button
                type="button"
                onClick={scaricaLogista}
                title="Da caricare sul portale Logista (non in TabaUno)"
              >
                Scarica Ordine_Logista.xls
              </button>
              <button
                type="button"
                onClick={inviaALogista}
                disabled={logistaInCorso || attesa}
                title="Carica le righe nella proposta WebT e INVIA l'ordine a Logista in modo definitivo."
              >
                {logistaInCorso ? 'In corso…' : 'Carica e invia a Logista'}
              </button>
              <button
                type="button"
                onClick={depositaInTabauno}
                disabled={deposito || attesa || online !== true}
                title="Scrive Ordine_Logista.xls nella cartella TabaUno del PC negozio. Non popola la griglia ordine di TabaUno."
              >
                {deposito ? 'Deposito…' : 'Deposita in TabaUno'}
              </button>
              <button type="button" className="is-primary" onClick={copiaElenco}>
                {copiato ? 'Copiato' : 'Copia elenco'}
              </button>
            </div>
          </div>
          <textarea ref={copiaRef} className="tab-copy-fallback" readOnly aria-hidden="true" tabIndex={-1} />
        </>
      )}
    </div>
  );
}
