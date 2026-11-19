import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Minus, Plus, Wifi } from 'lucide-react';
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

const FILTRI = [
  { id: 'tutti', label: 'Tutti' },
  { id: 'ordinare', label: 'Da ordinare' },
  { id: 'occhio', label: 'Occhio' },
  { id: 'coperti', label: 'Coperti' },
];

const ORDINE_GRUPPO = { ordinare: 0, occhio: 1, coperti: 2 };

const ETICHETTE_GRUPPO = {
  ordinare: 'Da ordinare',
  occhio: 'Occhio',
  coperti: 'Coperto',
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

function mediaTesto(value, digits = 2) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('it-IT', { maximumFractionDigits: digits });
}

function confronta(a, b, chiave, direzione) {
  const segno = direzione === 'asc' ? 1 : -1;
  const va = a[chiave];
  const vb = b[chiave];
  if (va == null && vb == null) return 0;
  if (va == null) return 1;
  if (vb == null) return -1;
  if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * segno;
  return String(va).localeCompare(String(vb), 'it') * segno;
}

export default function OrdineGratta() {
  const oggi = isoLocale(new Date());
  const [online, setOnline] = useState(null);
  const [preordine, setPreordine] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [errore, setErrore] = useState('');
  const [invio, setInvio] = useState(false);
  const [filtroGruppo, setFiltroGruppo] = useState('tutti');
  const [ordinamento, setOrdinamento] = useState({ chiave: 'giorni_coperti', direzione: 'asc' });
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
        const bozza = (d.preordini || []).find(row => (
          row.stato === 'bozza'
          || row.stato === 'errore'
          || row.stato === 'inviato_n8n'
          || row.stato === 'carrello_pronto'
        ));
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

  const conteggi = useMemo(() => {
    const righe = preordine?.righe || [];
    const out = { tutti: righe.length, ordinare: 0, occhio: 0, coperti: 0 };
    for (const riga of righe) {
      if (out[riga.gruppo] != null) out[riga.gruppo] += 1;
    }
    return out;
  }, [preordine]);

  const righe = useMemo(() => {
    let lista = [...(preordine?.righe || [])];
    if (filtroGruppo !== 'tutti') lista = lista.filter(r => r.gruppo === filtroGruppo);
    const { chiave, direzione } = ordinamento;
    lista.sort((a, b) => {
      if (chiave === 'gruppo') {
        const ga = ORDINE_GRUPPO[a.gruppo] ?? 9;
        const gb = ORDINE_GRUPPO[b.gruppo] ?? 9;
        if (ga !== gb) return (ga - gb) * (direzione === 'asc' ? 1 : -1);
      }
      const cmp = confronta(a, b, chiave, direzione);
      if (cmp !== 0) return cmp;
      return (ORDINE_GRUPPO[a.gruppo] ?? 9) - (ORDINE_GRUPPO[b.gruppo] ?? 9)
        || (a.giorni_coperti ?? 9999) - (b.giorni_coperti ?? 9999)
        || String(a.descrizione || '').localeCompare(String(b.descrizione || ''), 'it');
    });
    return lista;
  }, [preordine, filtroGruppo, ordinamento]);

  const totale = useMemo(() => totaleOrdine(preordine?.righe || []), [preordine]);
  const bloccato = preordine && !preordine.modificabile;
  const distanza = preordine
    ? giorniAllaConsegna(oggi, preordine.ultimo_giorno_chiuso, preordine.data_consegna)
    : 0;

  const ordina = (chiave) => {
    setOrdinamento(prev => (
      prev.chiave === chiave
        ? { chiave, direzione: prev.direzione === 'asc' ? 'desc' : 'asc' }
        : { chiave, direzione: chiave === 'descrizione' ? 'asc' : 'asc' }
    ));
  };

  const freccia = (chiave) => {
    if (ordinamento.chiave !== chiave) return '';
    return ordinamento.direzione === 'asc' ? ' ↑' : ' ↓';
  };

  const intestazione = (chiave, titolo, sotto = '', classe = 'grt-col-num') => (
    <th className={classe}>
      <button
        type="button"
        className={`tab-sort gia-sort ${ordinamento.chiave === chiave ? 'active' : ''}`}
        onClick={() => ordina(chiave)}
      >
        <span className="gia-th-main">{titolo}{freccia(chiave)}</span>
        {sotto ? <span className="gia-th-sub">{sotto}</span> : null}
      </button>
    </th>
  );

  return (
    <div className="tab-page gratta-page">
      <header className="tab-header">
        <div>
          <h1>Ordine Gratta e Vinci</h1>
          <p className="tab-sub">
            {preordine?.letto_alle
              ? `Dati TabaUno letti alle ${oraLetta(preordine.letto_alle)}`
              : 'Lettura vendite e giacenze dal PC negozio'}
          </p>
        </div>
      </header>

      {errore && <div className="tab-error">{errore}</div>}
      {preordine && !preordine.modificabile && (
        <div className="tab-ok">
          {STATI[preordine.stato] || preordine.stato}
          {preordine.messaggio_stato ? ` — ${preordine.messaggio_stato}` : ''}
        </div>
      )}

      <div className="tab-controls gia-controls grt-controls">
        {preordine && (
          <>
            <div className="tab-control">
              <span className="tab-label">Copre (giorni)</span>
              <div className="grt-days" role="group" aria-label="Giorni di copertura">
                {GIORNI.map(giorni => (
                  <button
                    key={giorni}
                    type="button"
                    className={`grt-day-btn ${preordine.giorni_copertura === giorni ? 'active' : ''}`}
                    disabled={bloccato}
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
                disabled={bloccato}
                onChange={e => aggiornaParametri({ data_consegna: e.target.value })}
              />
            </div>
            <div className="tab-control gia-control-filtri">
              <div className="gia-filtri" role="group" aria-label="Filtra per gruppo">
                {FILTRI.map(filtro => (
                  <button
                    key={filtro.id}
                    type="button"
                    className={`gia-filtro-btn grt-filtro-${filtro.id} ${filtroGruppo === filtro.id ? 'active' : ''}`}
                    onClick={() => setFiltroGruppo(filtro.id)}
                  >
                    <span className="gia-filtro-dot" aria-hidden="true" />
                    <span className="gia-filtro-label">{filtro.label}</span>
                    <span className="gia-filtro-count">{conteggi[filtro.id] || 0}</span>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
        <div className="tab-control gia-control-leggi">
          <button
            type="button"
            className="tab-btn primary gia-btn-leggi"
            onClick={leggi}
            disabled={attesa || online !== true}
            title={online === true ? 'PC remoto raggiungibile' : 'PC remoto non raggiungibile'}
          >
            <Wifi size={16} aria-hidden="true" />
            {attesa ? 'Lettura…' : preordine ? 'Aggiorna da PC' : 'Leggi da PC'}
          </button>
        </div>
      </div>

      {!preordine && !attesa && (
        <p className="tab-empty">
          {online === true
            ? 'Premi «Leggi da PC» per calcolare l’ordine Gratta e Vinci.'
            : 'Il PC remoto non è raggiungibile: avvia TabaUnoAgent e riprova.'}
        </p>
      )}

      {preordine && (
        <>
          <p className="grt-frase">
            {fraseCopertura(preordine.data_consegna, distanza, preordine.giorni_copertura)}
          </p>
          <div className="gia-sep" aria-hidden="true" />

          <div className="tab-table-wrap gia-table-wrap">
            <table className="tab-table gia-table grt-table">
              <thead>
                <tr>
                  {intestazione('descrizione', 'Gioco', '', 'gia-col-articolo')}
                  {intestazione('giacenza', 'Giacenza', 'oggi')}
                  {intestazione('media', 'Media', 'pz/giorno')}
                  {intestazione('giorni_coperti', 'Coperti', 'dopo consegna')}
                  {intestazione('pacchi', 'Pacchi', 'ordine')}
                  {intestazione('importo', 'Importo')}
                  {intestazione('gruppo', 'Stato', '', 'gia-col-stato')}
                </tr>
              </thead>
              <tbody>
                {righe.map(riga => (
                  <tr key={riga.codice} className={`gia-row grt-row grt-${riga.gruppo}`}>
                    <td className="gia-col-articolo">
                      <span className="gia-nome">{riga.descrizione || '—'}</span>
                      <span className="grt-meta">
                        {riga.codice}
                        {riga.corretto_a_mano ? ' · corretto' : ''}
                        {riga.escluso ? ' · escluso' : ''}
                        {Number(riga.giorni_esauriti) > 0 ? ` · ${riga.giorni_esauriti} gg esaurito` : ''}
                      </span>
                    </td>
                    <td className="gia-col-num">{mediaTesto(riga.giacenza, 0)}</td>
                    <td className="gia-col-num">
                      {mediaTesto(riga.media, 1)}
                      {(riga.settimane || []).length > 0 && (
                        <span className="gia-trend">{(riga.settimane || []).join(' · ')}</span>
                      )}
                    </td>
                    <td className="gia-col-num">
                      {riga.giorni_coperti == null ? '—' : mediaTesto(riga.giorni_coperti, 1)}
                    </td>
                    <td className="gia-col-num grt-col-pacchi">
                      <div className="grt-step">
                        <button
                          type="button"
                          aria-label="Meno un pacco"
                          disabled={bloccato}
                          onClick={() => cambiaPacchi(riga.codice, -1)}
                        >
                          <Minus size={16} />
                        </button>
                        <b>{riga.pacchi}</b>
                        <button
                          type="button"
                          aria-label="Più un pacco"
                          disabled={bloccato}
                          onClick={() => cambiaPacchi(riga.codice, 1)}
                        >
                          <Plus size={16} />
                        </button>
                      </div>
                    </td>
                    <td className="gia-col-num">{euro(riga.importo)}</td>
                    <td className="gia-col-stato">
                      <span className={`gia-badge grt-badge grt-${riga.gruppo}`}>
                        {ETICHETTE_GRUPPO[riga.gruppo] || riga.gruppo}
                      </span>
                    </td>
                  </tr>
                ))}
                {!righe.length && (
                  <tr>
                    <td colSpan={7} className="tab-empty-cell">
                      Nessun gioco in questo filtro.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

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
