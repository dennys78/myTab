import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Minus, Plus } from 'lucide-react';
import { apiFetch } from './api';
import {
  GIORNI,
  domaniIso,
  fraseCopertura,
  giorniAllaConsegna,
  isoLocale,
  ricalcolaRighe,
  totaleOrdine,
} from './grattaCalc';

const STATI = {
  bozza: 'Bozza',
  inviato_n8n: 'Inviato al bot',
  carrello_pronto: 'Carrello pronto',
  confermato: 'Confermato',
  inviato_portale: 'Inviato al portale',
  annullato: 'Annullato',
  errore: 'Errore',
};

function oraLetta(iso) {
  if (!iso) return '';
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return '';
  return data.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}

function euro(value) {
  return `${Number(value || 0).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

function mediaTesto(value) {
  const n = Number(value || 0);
  return n.toLocaleString('it-IT', { maximumFractionDigits: 2 });
}

export default function OrdineGratta() {
  const oggi = isoLocale(new Date());
  const [online, setOnline] = useState(null);
  const [preordine, setPreordine] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [errore, setErrore] = useState('');
  const [invio, setInvio] = useState(false);
  const [copertiAperti, setCopertiAperti] = useState(false);
  const pollRef = useRef(null);
  const saveRef = useRef(null);

  const ferma = () => {
    if (pollRef.current) clearTimeout(pollRef.current);
    if (saveRef.current) clearTimeout(saveRef.current);
  };

  useEffect(() => () => ferma(), []);

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
    const response = await apiFetch(`/api/gratta/preordini/${id}/`);
    const data = await response.json();
    if (data.status === 'success') {
      setPreordine(data.preordine);
      setOnline(data.preordine.agent_online);
    }
  }, []);

  useEffect(() => {
    apiFetch('/api/gratta/preordini/')
      .then(r => r.json())
      .then(d => {
        if (d.status !== 'success') return;
        setOnline(!!d.agent_online);
        const bozza = (d.preordini || []).find(row => row.stato === 'bozza' || row.stato === 'errore' || row.stato === 'inviato_n8n' || row.stato === 'carrello_pronto');
        if (bozza) apri(bozza.id);
      })
      .catch(() => {});
  }, [apri]);

  useEffect(() => {
    if (!preordine || preordine.modificabile) return undefined;
    const id = preordine.id;
    const timer = setInterval(() => apri(id), 4000);
    return () => clearInterval(timer);
  }, [preordine, apri]);

  const salva = useCallback((next, righePatch) => {
    if (saveRef.current) clearTimeout(saveRef.current);
    saveRef.current = setTimeout(async () => {
      const response = await apiFetch(`/api/gratta/preordini/${next.id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          giorni_copertura: next.giorni_copertura,
          data_consegna: next.data_consegna,
          righe: righePatch || next.righe.map(riga => ({ codice: riga.codice, pacchi: riga.pacchi })),
        }),
      });
      const data = await response.json();
      if (data.status === 'success') setPreordine(data.preordine);
      else setErrore(data.error || 'Salvataggio non riuscito.');
    }, 350);
  }, []);

  const aggiornaParametri = (patch) => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const giorni = patch.giorni_copertura ?? prev.giorni_copertura;
      const consegna = patch.data_consegna ?? prev.data_consegna;
      const righe = ricalcolaRighe(prev.righe, {
        giorniCopertura: giorni,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: consegna,
      });
      const next = { ...prev, giorni_copertura: giorni, data_consegna: consegna, righe };
      salva(next);
      return next;
    });
  };

  const cambiaPacchi = (codice, delta) => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const toccate = prev.righe.map(riga => (
        riga.codice === codice
          ? { ...riga, pacchi: Math.max(0, Number(riga.pacchi) + delta), corretto_a_mano: true }
          : riga
      ));
      const righe = ricalcolaRighe(toccate, {
        giorniCopertura: prev.giorni_copertura,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: prev.data_consegna,
      });
      const next = { ...prev, righe };
      salva(next, [{ codice, pacchi: righe.find(riga => riga.codice === codice).pacchi }]);
      return next;
    });
  };

  const annullaCorrezioni = () => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const pulite = prev.righe.map(riga => ({ ...riga, corretto_a_mano: false, pacchi: riga.pacchi_proposti }));
      const righe = ricalcolaRighe(pulite, {
        giorniCopertura: prev.giorni_copertura,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: prev.data_consegna,
      });
      const next = { ...prev, righe };
      salva(next);
      return next;
    });
  };

  const leggi = async () => {
    setErrore('');
    setAttesa(true);
    const response = await apiFetch('/api/gratta/preordini/', {
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
        const creato = await apiFetch(`/api/gratta/preordini/da-richiesta/${data.id}/`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ giorni_copertura: 7, data_consegna: domaniIso() }),
        });
        const ordine = await creato.json();
        setAttesa(false);
        if (ordine.status === 'success') setPreordine(ordine.preordine);
        else setErrore(ordine.error || 'Calcolo non riuscito.');
        return;
      }
      if (body.status === 'error' || body.status === 'expired') {
        setAttesa(false);
        setErrore(body.error || 'Il PC del negozio non ha completato la lettura.');
        return;
      }
      pollRef.current = setTimeout(poll, 2000);
    };
    poll();
  };

  const invia = async () => {
    if (!preordine) return;
    setInvio(true);
    setErrore('');
    const response = await apiFetch(`/api/gratta/preordini/${preordine.id}/invia/`, { method: 'POST' });
    const data = await response.json();
    setInvio(false);
    if (data.preordine) setPreordine(data.preordine);
    if (data.status !== 'success') setErrore(data.error || 'Invio non riuscito.');
  };

  const scarica = () => {
    if (preordine) window.location.assign(`/api/gratta/preordini/${preordine.id}/json/`);
  };

  const elimina = async () => {
    if (!preordine) return;
    if (!window.confirm('Eliminare questo ordine? Poi puoi rifare la lettura dal PC.')) return;
    setErrore('');
    const response = await apiFetch(`/api/gratta/preordini/${preordine.id}/`, { method: 'DELETE' });
    const data = await response.json().catch(() => ({}));
    if (response.ok && data.status === 'success') setPreordine(null);
    else setErrore(data.error || 'Eliminazione non riuscita.');
  };

  const gruppi = useMemo(() => {
    const righe = preordine?.righe || [];
    const perCopertura = (a, b) => (a.giorni_coperti ?? 9999) - (b.giorni_coperti ?? 9999);
    return {
      ordinare: righe.filter(riga => riga.gruppo === 'ordinare').sort(perCopertura),
      occhio: righe.filter(riga => riga.gruppo === 'occhio').sort(perCopertura),
      coperti: righe.filter(riga => riga.gruppo === 'coperti'),
    };
  }, [preordine]);

  const totale = useMemo(() => totaleOrdine(preordine?.righe || []), [preordine]);
  const bloccato = preordine && !preordine.modificabile;
  const distanza = preordine
    ? giorniAllaConsegna(oggi, preordine.ultimo_giorno_chiuso, preordine.data_consegna)
    : 0;

  return (
    <div className="gratta-page">
      <header className="gratta-top">
        <div>
          <h1>Ordine Gratta e Vinci</h1>
          <p className="gratta-meta">
            {preordine?.letto_alle ? `Dati TabaUno letti alle ${oraLetta(preordine.letto_alle)}` : 'Nessuna lettura ancora'}
            {' · '}
            PC negozio {online ? 'online' : online === false ? 'offline' : '…'}
          </p>
        </div>
        <button type="button" className="gratta-read" onClick={leggi} disabled={attesa || online !== true}>
          {attesa ? 'In attesa del PC…' : 'Leggi da PC'}
        </button>
      </header>

      {errore && <p className="gratta-error">{errore}</p>}
      {preordine && !preordine.modificabile && (
        <p className="gratta-status">
          {STATI[preordine.stato] || preordine.stato}
          {preordine.messaggio_stato ? ` — ${preordine.messaggio_stato}` : ''}
        </p>
      )}

      {preordine && (
        <>
          <section className="gratta-choices">
            <div>
              <span>L&apos;ordine deve coprire</span>
              <div className="gratta-days">
                {GIORNI.map(giorni => (
                  <button
                    key={giorni}
                    type="button"
                    className={preordine.giorni_copertura === giorni ? 'is-on' : ''}
                    disabled={bloccato}
                    onClick={() => aggiornaParametri({ giorni_copertura: giorni })}
                  >
                    {giorni}
                  </button>
                ))}
              </div>
            </div>
            <label>
              Consegna
              <input
                type="date"
                value={preordine.data_consegna}
                disabled={bloccato}
                onChange={e => aggiornaParametri({ data_consegna: e.target.value })}
              />
            </label>
          </section>
          <p className="gratta-frase">
            {fraseCopertura(preordine.data_consegna, distanza, preordine.giorni_copertura)}
          </p>

          <Gruppo titolo="Da ordinare" righe={gruppi.ordinare} vuoto="Nessun gioco da ordinare." onStep={cambiaPacchi} bloccato={bloccato} />
          <Gruppo titolo="Da tenere d'occhio" righe={gruppi.occhio} vuoto="Nessun gioco al limite." onStep={cambiaPacchi} bloccato={bloccato} />
          <section className="gratta-group">
            <button type="button" className="gratta-fold" onClick={() => setCopertiAperti(v => !v)}>
              Coperti ({gruppi.coperti.length}) {copertiAperti ? '▾' : '▸'}
            </button>
            {copertiAperti && <Lista righe={gruppi.coperti} onStep={cambiaPacchi} bloccato={bloccato} />}
          </section>

          <div className="gratta-dock">
            <div>
              <strong>{totale.giochi} giochi · {totale.pacchi} pacchi</strong>
              <span>Aggio 8% {euro(totale.aggio)}</span>
              <b>Totale ordine {euro(totale.importo)}</b>
              {totale.sottoMinimo && <em>Sotto il minimo di 900 €</em>}
            </div>
            <div className="gratta-dock-actions">
              <button type="button" className="is-danger" onClick={elimina}>Elimina ordine</button>
              <button type="button" onClick={annullaCorrezioni} disabled={bloccato}>Annulla correzioni</button>
              <button type="button" onClick={scarica}>Scarica JSON</button>
              <button type="button" className="is-primary" onClick={invia} disabled={bloccato || invio || totale.sottoMinimo}>
                {invio ? 'Invio…' : 'Invia al bot'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function Gruppo({ titolo, righe, vuoto, onStep, bloccato }) {
  return (
    <section className="gratta-group">
      <h2>{titolo}</h2>
      {righe.length === 0 ? <p className="gratta-empty">{vuoto}</p> : <Lista righe={righe} onStep={onStep} bloccato={bloccato} />}
    </section>
  );
}

function Lista({ righe, onStep, bloccato }) {
  return (
    <div className="gratta-list">
      {righe.map(riga => (
        <article key={riga.codice} className={`gratta-row is-${riga.gruppo}`}>
          <div className="gratta-row-main">
            <strong>{riga.codice} {riga.descrizione}</strong>
            <span>{euro(riga.prezzo)} · vende {mediaTesto(riga.media)}/giorno · giacenza {mediaTesto(riga.giacenza)}</span>
            <span className="gratta-weeks">{(riga.settimane || []).join(' · ')}</span>
            <span>
              {Number(riga.giorni_esauriti) > 0 ? `${riga.giorni_esauriti} gg esaurito · ` : ''}
              {riga.giorni_coperti == null ? 'nessuna vendita recente' : `${mediaTesto(riga.giorni_coperti)} gg coperti dopo la consegna`}
              {riga.corretto_a_mano ? ' · corretto' : ''}
              {riga.escluso ? ' · escluso' : ''}
            </span>
          </div>
          <div className="gratta-step">
            <button type="button" aria-label="Meno un pacco" disabled={bloccato} onClick={() => onStep(riga.codice, -1)}><Minus size={18} /></button>
            <b>{riga.pacchi}</b>
            <button type="button" aria-label="Più un pacco" disabled={bloccato} onClick={() => onStep(riga.codice, 1)}><Plus size={18} /></button>
            <small>{euro(riga.importo)}</small>
          </div>
        </article>
      ))}
    </div>
  );
}
