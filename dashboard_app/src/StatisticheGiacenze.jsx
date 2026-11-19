import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from './api';

const STATI_ORDINE = ['esaurito', 'prima_consegna', 'rischio', 'ok', 'fermo'];
const SOGLIE_MINIME = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
const SOGLIA_DEFAULT = 5;
const CHIP_LABEL = {
  esaurito: 'Esaurito',
  prima_consegna: 'Prima dell’ordine',
  rischio: 'Rischio',
  ok: 'Copre',
  fermo: 'Fermo',
};

function sottoSoglia(riga, soglia) {
  return Number(riga.alla_data) <= soglia;
}

function formattaChiusura(iso) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

/** Sabato della settimana in corso (lunedì–domenica). */
function sabatoSettimanaCorrente(oggi = new Date()) {
  const d = new Date(oggi.getFullYear(), oggi.getMonth(), oggi.getDate(), 12);
  const giorno = d.getDay(); // 0=dom … 6=sab
  const versoLunedi = giorno === 0 ? -6 : 1 - giorno;
  d.setDate(d.getDate() + versoLunedi + 5);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
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
  const [dataProiezione, setDataProiezione] = useState(() => sabatoSettimanaCorrente());
  const [filtroStato, setFiltroStato] = useState('tutti');
  const [sogliaMinima, setSogliaMinima] = useState(SOGLIA_DEFAULT);
  const [ricerca, setRicerca] = useState('');
  const [ordinamento, setOrdinamento] = useState({ chiave: 'alla_data', direzione: 'asc' });
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
      if (data) setDataProiezione(data);
      setErrore('');
    }
    return body;
  }, []);

  useEffect(() => {
    caricaAnalisi(null, sabatoSettimanaCorrente()).catch(() => {});
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
        await caricaAnalisi(data.id, dataProiezione || sabatoSettimanaCorrente());
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

  const rilevanti = useMemo(
    () => (analisi?.righe || []).filter(r => sottoSoglia(r, sogliaMinima)),
    [analisi, sogliaMinima],
  );

  const riepilogo = useMemo(() => {
    const conteggi = Object.fromEntries(STATI_ORDINE.map(s => [s, 0]));
    for (const riga of rilevanti) conteggi[riga.stato] = (conteggi[riga.stato] || 0) + 1;
    return conteggi;
  }, [rilevanti]);

  const righe = useMemo(() => {
    let lista = [...rilevanti];
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
        return base || confronta(a, b, 'alla_data', 'asc');
      });
    } else {
      lista.sort((a, b) => confronta(a, b, chiave, direzione));
    }
    return lista;
  }, [rilevanti, filtroStato, ricerca, ordinamento]);

  const ordina = (chiave) => {
    setOrdinamento(prev => (
      prev.chiave === chiave
        ? { chiave, direzione: prev.direzione === 'asc' ? 'desc' : 'asc' }
        : { chiave, direzione: 'asc' }
    ));
  };

  const freccia = (chiave) => {
    if (ordinamento.chiave !== chiave) return '';
    return ordinamento.direzione === 'asc' ? ' ↑' : ' ↓';
  };

  const intestazione = (chiave, titolo, sotto = '') => (
    <th className={chiave === 'descrizione' ? 'gia-col-articolo' : 'gia-col-num'}>
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
    <div className="tab-page gia-page">
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
            className="tab-btn primary gia-btn-leggi"
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
          <div className="tab-controls gia-controls">
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
              <span className="tab-label">Mostra se ≤</span>
              <select
                value={sogliaMinima}
                onChange={e => setSogliaMinima(Number(e.target.value))}
                aria-label="Giacenza minima da mostrare"
              >
                {SOGLIE_MINIME.map(n => (
                  <option key={n} value={n}>{n} pz</option>
                ))}
              </select>
            </div>
            <div className="tab-control gia-control-cerca">
              <span className="tab-label">Cerca</span>
              <input
                type="search"
                value={ricerca}
                placeholder="Codice, nome, famiglia…"
                onChange={e => setRicerca(e.target.value)}
              />
            </div>
          </div>

          <div className="gia-filtri" role="group" aria-label="Filtra per stato">
            <button
              type="button"
              className={`gia-chip gia-tutti ${filtroStato === 'tutti' ? 'active' : ''}`}
              onClick={() => setFiltroStato('tutti')}
            >
              <span className="gia-chip-dot" aria-hidden="true" />
              <span className="gia-chip-label">In elenco</span>
              <span className="gia-chip-count">{rilevanti.length}</span>
            </button>
            {STATI_ORDINE.map(stato => (
              <button
                key={stato}
                type="button"
                className={`gia-chip gia-${stato} ${filtroStato === stato ? 'active' : ''}`}
                onClick={() => setFiltroStato(stato)}
              >
                <span className="gia-chip-dot" aria-hidden="true" />
                <span className="gia-chip-label">{CHIP_LABEL[stato] || etichette[stato]}</span>
                <span className="gia-chip-count">{riepilogo[stato] || 0}</span>
              </button>
            ))}
          </div>

          <div className="tab-table-wrap gia-table-wrap">
            <table className="tab-table gia-table">
              <thead>
                <tr>
                  {intestazione('descrizione', 'Articolo')}
                  {intestazione('giacenza', 'Giacenza', 'oggi')}
                  {intestazione('media', 'Media', 'pz/giorno')}
                  {intestazione('venduto_4_settimane', 'Venduto', '4 settimane')}
                  {intestazione('data_fine', 'Fine stimata per il')}
                  {intestazione('alla_data', 'Stimati', formattaChiusura(analisi.data_proiezione))}
                  {intestazione('stato', 'Stato')}
                </tr>
              </thead>
              <tbody>
                {righe.map(riga => (
                  <tr key={riga.aams} className={`gia-row gia-${riga.stato}`}>
                    <td className="gia-col-articolo">
                      <div className="tab-articolo">
                        <span className="tab-aams">{riga.aams}</span>
                        <span className="tab-nome">{riga.descrizione}</span>
                      </div>
                    </td>
                    <td className="gia-col-num">{formattaNumero(riga.giacenza, 0)}</td>
                    <td className="gia-col-num">{formattaNumero(riga.media, 1)}</td>
                    <td className="gia-col-num">
                      {formattaNumero(riga.venduto_4_settimane, 0)}
                      {riga.trend_pct != null && (
                        <span className={`gia-trend ${riga.trend_pct >= 0 ? 'up' : 'down'}`}>
                          {riga.trend_pct > 0 ? '+' : ''}{riga.trend_pct}%
                        </span>
                      )}
                    </td>
                    <td className="gia-col-num">{riga.data_fine ? formattaChiusura(riga.data_fine) : '—'}</td>
                    <td className={`gia-col-num ${Number(riga.alla_data) < 0 ? 'gia-neg' : ''}`}>
                      {formattaNumero(riga.alla_data, 0)}
                      {riga.mancanti_alla_data > 0 && (
                        <span className="gia-manca"> (−{riga.mancanti_alla_data})</span>
                      )}
                    </td>
                    <td className="gia-col-stato">
                      <span className={`gia-badge gia-${riga.stato}`}>{etichette[riga.stato]}</span>
                    </td>
                  </tr>
                ))}
                {!righe.length && (
                  <tr>
                    <td colSpan={7} className="tab-empty-cell">
                      Nessun articolo con giacenza stimata ≤ {sogliaMinima} pz
                      {filtroStato !== 'tutti' ? ' per questo stato' : ''}.
                    </td>
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
