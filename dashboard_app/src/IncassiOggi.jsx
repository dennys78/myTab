import React, { useCallback, useEffect, useState } from 'react';
import { Loader2, Wifi } from 'lucide-react';
import { apiFetch } from './api';

const ORDINE = ['tabacchi', 'gratta', 'lottomatica', 'caffe', 'rosticceria', 'pasticceria'];

function formattaEuro(value) {
  return `${Number(value || 0).toLocaleString('it-IT', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} €`;
}

function formattaData(iso) {
  if (!iso) return '—';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

function formattaOra(value) {
  if (!value) return '';
  if (String(value).includes('T')) {
    const dt = new Date(value);
    if (!Number.isNaN(dt.getTime())) {
      return dt.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
    }
  }
  return String(value).slice(0, 5);
}

export default function IncassiOggi() {
  const [online, setOnline] = useState(null);
  const [dati, setDati] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [errore, setErrore] = useState('');
  const [caricato, setCaricato] = useState(false);

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

  const aggiorna = useCallback(async () => {
    setErrore('');
    setAttesa(true);
    try {
      const response = await apiFetch('/api/incassi/parziali/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      const body = await response.json();
      if (body.agent_online !== undefined) setOnline(!!body.agent_online);
      if (!response.ok || body.status !== 'success') {
        setDati(null);
        setErrore(body.error || 'Incassi non disponibili.');
      } else {
        setDati(body);
        setErrore('');
      }
    } catch {
      setErrore('Incassi non disponibili.');
      setDati(null);
    } finally {
      setAttesa(false);
      setCaricato(true);
    }
  }, []);

  useEffect(() => {
    aggiorna();
  }, [aggiorna]);

  return (
    <div className="tab-page gia-page incassi-page">
      <header className="tab-header">
        <div>
          <h1>Incassi di oggi</h1>
          <p className="tab-sub">
            Parziali Tabacchi, Gratta e Vinci, Lottomatica, Caffè, Rosticceria e Pasticceria
          </p>
        </div>
      </header>

      <div className="tab-controls gia-controls">
        <div className="tab-control">
          <span className="tab-label">Giorno</span>
          <div className="incassi-meta-pill">
            {dati ? formattaData(dati.data) : '—'}
          </div>
        </div>
        <div className="tab-control">
          <span className="tab-label">Ultima vendita</span>
          <div className="incassi-meta-pill">
            {dati?.ultima_ora || '—'}
          </div>
        </div>
        <div className="tab-control">
          <span className="tab-label">Letto alle</span>
          <div className="incassi-meta-pill">
            {dati?.letto_alle ? formattaOra(dati.letto_alle) : '—'}
          </div>
        </div>
        <div className="tab-control">
          <span className="tab-label">PC negozio</span>
          <div className={`incassi-meta-pill ${online === true ? 'ok' : online === false ? 'ko' : ''}`}>
            {online == null ? '…' : online ? 'online' : 'offline'}
          </div>
        </div>
        <div className="tab-control gia-control-leggi">
          <button
            type="button"
            className="tab-btn primary gia-btn-leggi"
            onClick={aggiorna}
            disabled={attesa || online !== true}
            title={online === true ? 'PC remoto raggiungibile' : 'PC remoto non raggiungibile'}
          >
            {attesa ? <Loader2 size={16} className="incassi-spin" aria-hidden="true" /> : <Wifi size={16} aria-hidden="true" />}
            {attesa ? 'Lettura…' : 'Aggiorna'}
          </button>
        </div>
      </div>

      {errore && <div className="tab-error">{errore}</div>}

      {dati?.cassa_non_oggi && (
        <div className="tab-ok" style={{ borderColor: '#f59e0b', color: '#b45309', background: 'rgba(245,158,11,0.12)' }}>
          ⚠️ La cassa del {formattaData(dati.data)} non risulta ancora chiusa rispetto a oggi.
        </div>
      )}

      {!dati && caricato && !attesa && !errore && (
        <p className="tab-empty">Nessun dato disponibile.</p>
      )}

      {dati && (
        <>
          <div className="gia-sep" aria-hidden="true" />
          {dati.nessuna_vendita ? (
            <p className="tab-empty">Nessuna vendita registrata dalla chiusura precedente.</p>
          ) : (
            <div className="incassi-grid">
              {ORDINE.map(chiave => {
                const s = dati.settori?.[chiave];
                if (!s) return null;
                return (
                  <div key={chiave} className={`incassi-card incassi-${chiave}`}>
                    <div className="incassi-card-top">
                      <span className="incassi-emoji" aria-hidden="true">{s.emoji}</span>
                      <span className="incassi-label">{s.label}</span>
                    </div>
                    <div className="incassi-importo">{formattaEuro(s.importo)}</div>
                    <div className="incassi-n">{s.n} vendit{s.n === 1 ? 'a' : 'e'}</div>
                  </div>
                );
              })}
              <div className="incassi-card incassi-totale">
                <div className="incassi-card-top">
                  <span className="incassi-emoji" aria-hidden="true">💶</span>
                  <span className="incassi-label">Totale settori</span>
                </div>
                <div className="incassi-importo">{formattaEuro(dati.totale)}</div>
                <div className="incassi-n">somma dei 6 settori</div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
