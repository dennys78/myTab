import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from './api';

const STATI_ORDINE = ['esaurito', 'prima_consegna', 'rischio', 'ok', 'fermo'];

function formattaChiusura(iso) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

function formattaNumero(value, digits = 1) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('it-IT', { minimumFractionDigits: 0, maximumFractionDigits: digits });
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

export default function StatisticheGiacenze() {
  const [online, setOnline] = useState(null);
  const [analisi, setAnalisi] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [errore, setErrore] = useState('');
  const [dataProiezione, setDataProiezione] = useState('');
  const [filtroStato, setFiltroStato] = useState('tutti');
  const [ricerca, setRicerca] = useState('');
  const [ordinamento, setOrdinamento] = useState({ chiave: 'stato', direzione: 'asc' });
  const pollRef = useRef(null);

  const ferma = () => {
    if (pollRef.current) clearTimeout(pollRef.current);
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

  const caricaAnalisi = useCallback(async (id, data) => {
    const params = new URLSearchParams();
    if (id) params.set('request_id', String(id));
    if (data) params.set('data', data);
    const response = await apiFetch(`/api/statistiche/giacenze/?${params}`);
    const body = await response.json();
    if (body.agent_online !== undefined) setOnline(!!body.agent_online);
    if (body.status !== 'success') {
      setErrore(body.error || 'Analisi non disponibile.');
      return null;
    }
    if (body.pronta && body.analisi) {
      setAnalisi(body.analisi);
      setRequestId(body.request_id);
      if (!data) setDataProiezione(body.analisi.data_proiezione);
      setErrore('');
    }
    return body;
  }, []);

  useEffect(() => {
    caricaAnalisi(null, '').catch(() => {});
  }, [caricaAnalisi]);

  const leggi = async () => {
    setErrore('');
    setAttesa(true);
    ferma();
    const response = await apiFetch('/api/statistiche/giacenze/lettura/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const data = await response.json();
    if (data.status !== 'success') {
      setAttesa(false);
      setOnline(data.agent_online === undefined ? online : !!data.agent_online);
      setErrore(data.error || 'Richiesta non accodata.');
      return;
    }
    setOnline(!!data.agent_online);
    setRequestId(data.id);
    const poll = async () => {
      const stato = await apiFetch(`/api/tabauno/requests/${data.id}/`);
      const body = await stato.json();
      setOnline(!!body.agent_online);
      if (body.status === 'done') {
        await caricaAnalisi(data.id, dataProiezione);
        setAttesa(false);
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

  const cambiaData = async (value) => {
    setDataProiezione(value);
    if (!requestId && !analisi) return;
    setErrore('');
    await caricaAnalisi(requestId, value);
  };

  const etichette = analisi?.etichette_stato || {
    esaurito: 'Esaurito',
    prima_consegna: 'Finisce prima dell’ordine',
    rischio: 'Rischio',
    ok: 'Copre',
    fermo: 'Fermo',
  };

  const righe = useMemo(() => {
    let lista = [...(analisi?.righe || [])];
    if (filtroStato !== 'tutti') lista = lista.filter(r => r.stato === filtroStato);
    const q = ricerca.trim().toLowerCase();
    if (q) {
      lista = lista.filter(r =>
        String(r.aams).toLowerCase().includes(q)
        || String(r.descrizione).toLowerCase().includes(q)
        || String(r.famiglia).toLowerCase().includes(q));
    }
    const { chiave, direzione } = ordinamento;
    if (chiave === 'stato') {
      lista.sort((a, b) => {
        const ia = STATI_ORDINE.indexOf(a.stato);
        const ib = STATI_ORDINE.indexOf(b.stato);
        const base = (ia - ib) * (direzione === 'asc' ? 1 : -1);
        return base || confronta(a, b, 'giorni_fine', 'asc');
      });
    } else {
      lista.sort((a, b) => confronta(a, b, chiave, direzione));
    }
    return lista;
  }, [analisi, filtroStato, ricerca, ordinamento]);

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

  const riepilogo = analisi?.riepilogo || {};

  return (
    <div className="tab-page">
      <header className="tab-header">
        <div>
          <h1>Giacenze</h1>
          <p className="tab-sub">
            {analisi?.ultimo_giorno_chiuso
              ? `Vendite delle ultime 4 settimane · chiusura del ${formattaChiusura(analisi.ultimo_giorno_chiuso)}`
              : 'Vendite delle ultime 4 settimane · proiezione giacenze'}
          </p>
          <p className={`tab-pc ${online ? 'online' : online === false ? 'offline' : ''}`}>
            PC negozio: {online == null ? '…' : online ? 'online' : 'offline'}
          </p>
        </div>
        <div className="tab-header-actions">
          <button
            type="button"
            className="tab-btn"
            onClick={leggi}
            disabled={attesa || online !== true}
          >
            {attesa ? 'Lettura…' : analisi ? 'Aggiorna da PC' : 'Leggi da PC'}
          </button>
        </div>
      </header>

      {errore && <div className="tab-error">{errore}</div>}

      {!analisi && !attesa && (
        <p className="tab-empty">Premi «Leggi da PC» quando il servizio TabaUnoAgent è online.</p>
      )}

      {analisi && (
        <>
          <div className="tab-controls">
            <div className="tab-control">
              <span className="tab-label">Giacenza stimata al</span>
              <input
                type="date"
                value={dataProiezione || analisi.data_proiezione}
                min={new Date().toISOString().slice(0, 10)}
                onChange={e => cambiaData(e.target.value)}
              />
            </div>
            <div className="tab-control">
              <span className="tab-label">Prossimo ordine</span>
              <strong>{formattaChiusura(analisi.consegna)}</strong>
              <span className="tab-hint-inline">tra {analisi.giorni_alla_consegna} gg</span>
            </div>
            <div className="tab-control tab-control-grow">
              <span className="tab-label">Cerca</span>
              <input
                type="search"
                value={ricerca}
                placeholder="Codice, nome, famiglia…"
                onChange={e => setRicerca(e.target.value)}
              />
            </div>
          </div>
          <p className="tab-hint">
            La colonna «Al {formattaChiusura(analisi.data_proiezione)}» stima i pezzi rimanenti a quella data
            con il ritmo medio delle ultime 4 settimane. Lo stato segnala chi finisce prima del prossimo ordine
            ({formattaChiusura(analisi.consegna)}).
          </p>

          <div className="gia-riepilogo" role="group" aria-label="Riepilogo stati">
            <button
              type="button"
              className={`gia-chip ${filtroStato === 'tutti' ? 'active' : ''}`}
              onClick={() => setFiltroStato('tutti')}
            >
              Tutti <strong>{analisi.righe.length}</strong>
            </button>
            {STATI_ORDINE.map(stato => (
              <button
                key={stato}
                type="button"
                className={`gia-chip gia-${stato} ${filtroStato === stato ? 'active' : ''}`}
                onClick={() => setFiltroStato(stato)}
              >
                {etichette[stato]} <strong>{riepilogo[stato] || 0}</strong>
              </button>
            ))}
          </div>

          <div className="tab-table-wrap">
            <table className="tab-table">
              <thead>
                <tr>
                  <th className="tab-col-articolo">
                    <button type="button" className="tab-sort" onClick={() => ordina('descrizione')}>
                      Articolo{freccia('descrizione')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('giacenza')}>
                      Giacenza{freccia('giacenza')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('media')}>
                      Media/gg{freccia('media')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('venduto_4_settimane')}>
                      4 sett.{freccia('venduto_4_settimane')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('data_fine')}>
                      Finisce{freccia('data_fine')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('alla_data')}>
                      Al {formattaChiusura(analisi.data_proiezione)}{freccia('alla_data')}
                    </button>
                  </th>
                  <th>
                    <button type="button" className="tab-sort" onClick={() => ordina('stato')}>
                      Stato{freccia('stato')}
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody>
                {righe.map(riga => (
                  <tr key={riga.aams} className={`gia-row gia-${riga.stato}`}>
                    <td className="tab-col-articolo">
                      <div className="tab-articolo">
                        <span className="tab-aams">{riga.aams}</span>
                        <span className="tab-nome">{riga.descrizione}</span>
                      </div>
                    </td>
                    <td>{formattaNumero(riga.giacenza)}</td>
                    <td>{formattaNumero(riga.media, 2)}</td>
                    <td>
                      {formattaNumero(riga.venduto_4_settimane)}
                      {riga.trend_pct != null && (
                        <span className={`gia-trend ${riga.trend_pct >= 0 ? 'up' : 'down'}`}>
                          {riga.trend_pct > 0 ? '+' : ''}{riga.trend_pct}%
                        </span>
                      )}
                    </td>
                    <td>{riga.data_fine ? formattaChiusura(riga.data_fine) : '—'}</td>
                    <td className={Number(riga.alla_data) < 0 ? 'gia-neg' : ''}>
                      {formattaNumero(riga.alla_data)}
                      {riga.mancanti_alla_data > 0 && (
                        <span className="gia-manca"> −{riga.mancanti_alla_data}</span>
                      )}
                    </td>
                    <td>
                      <span className={`gia-badge gia-${riga.stato}`}>{etichette[riga.stato]}</span>
                    </td>
                  </tr>
                ))}
                {!righe.length && (
                  <tr>
                    <td colSpan={7} className="tab-empty-cell">Nessun articolo con questo filtro.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
