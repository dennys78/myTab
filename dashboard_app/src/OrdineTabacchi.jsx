import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronRight, Minus, Plus, Trash2 } from 'lucide-react';
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
  fraseCopertura,
  formattaChiusura,
  formattaFinisce,
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

export default function OrdineTabacchi() {
  const oggi = isoLocale(new Date());
  const [online, setOnline] = useState(null);
  const [preordine, setPreordine] = useState(null);
  const [attesa, setAttesa] = useState(false);
  const [errore, setErrore] = useState('');
  const [altriAperti, setAltriAperti] = useState(false);
  const [ricerca, setRicerca] = useState('');
  const [copiato, setCopiato] = useState(false);
  const [ordinamento, setOrdinamento] = useState({ chiave: 'finisce', direzione: 'asc' });
  const [sezione, setSezione] = useState('tabacchi');
  const pollRef = useRef(null);
  const saveRef = useRef(null);
  const copiaRef = useRef(null);

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
    const response = await apiFetch(`/api/tabacchi/preordini/${id}/`);
    const data = await response.json();
    if (data.status === 'success') {
      setPreordine(data.preordine);
      setOnline(data.preordine.agent_online);
    }
  }, []);

  useEffect(() => {
    apiFetch('/api/tabacchi/preordini/')
      .then(r => r.json())
      .then(d => {
        if (d.status !== 'success') return;
        setOnline(!!d.agent_online);
        const bozza = (d.preordini || []).find(row => row.stato === 'bozza' || row.stato === 'esportato');
        if (bozza) apri(bozza.id);
      })
      .catch(() => {});
  }, [apri]);

  const salva = useCallback((next, righePatch) => {
    if (saveRef.current) clearTimeout(saveRef.current);
    saveRef.current = setTimeout(async () => {
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
    }, 350);
  }, []);

  const aggiornaParametri = (patch) => {
    setPreordine(prev => {
      if (!prev?.modificabile) return prev;
      const giorni = patch.giorni_copertura ?? prev.giorni_copertura;
      const consegna = patch.data_consegna ?? prev.data_consegna;
      const scortaPct = normalizzaScortaPct(patch.scorta_pct ?? prev.scorta_pct ?? DEFAULT_SCORTA_PCT);
      const righe = ricalcolaRighe(prev.righe, {
        giorniCopertura: giorni,
        oggi,
        ultimoChiuso: prev.ultimo_giorno_chiuso,
        dataConsegna: consegna,
        scortaPct,
      });
      const totali = totaliOrdine(righe);
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
          body: JSON.stringify({ giorni_copertura: 7, scorta_pct: DEFAULT_SCORTA_PCT, data_consegna: consegna }),
        });
        const ordine = await creato.json();
        setAttesa(false);
        if (ordine.status === 'success') setPreordine(ordine.preordine);
        else setErrore(ordine.error || 'Calcolo non riuscito.');
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

  const rigaTabella = (riga, { conStepper = true } = {}) => (
    <tr key={riga.aams} className={Number(riga.unita) > 0 ? 'tab-row-order' : undefined}>
      <td className="tab-col-articolo" title={riga.descrizione}>
        <span className="tab-aams">{riga.aams}</span>
        <span className="tab-nome">{riga.descrizione}</span>
        <div className="tab-mobile-meta">
          <span>{Number(riga.giacenza).toLocaleString('it-IT')}</span>
          <span>·</span>
          <span>{mediaTesto(riga.media)}</span>
          <span>·</span>
          <span className={`tab-finisce tab-finisce--${riga.urgenza}`}>{formattaFinisce(riga.data_fine)}</span>
        </div>
      </td>
      <td className="tab-num tab-desktop-only">{Number(riga.giacenza).toLocaleString('it-IT')}</td>
      <td className="tab-num tab-desktop-only">{mediaTesto(riga.media)}</td>
      <td className={`tab-num tab-desktop-only tab-finisce tab-finisce--${riga.urgenza}`}>
        {formattaFinisce(riga.data_fine)}
      </td>
      <td className="tab-stecche">
        {conStepper ? (
          <div className="tab-stepper">
            <button type="button" onClick={() => cambiaUnita(riga.aams, -1)} disabled={!preordine?.modificabile} aria-label="Diminuisci">
              <Minus size={14} />
            </button>
            <span className={riga.corretto_a_mano ? 'tab-step-manual' : (Number(riga.unita) > 0 ? 'tab-step-on' : '')}>
              {Number(riga.unita) || 0}
            </span>
            <button type="button" onClick={() => cambiaUnita(riga.aams, 1)} disabled={!preordine?.modificabile} aria-label="Aumenta">
              <Plus size={14} />
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
          <button type="button" className="tab-add" onClick={() => cambiaUnita(riga.aams, 1)} disabled={!preordine?.modificabile}>
            <Plus size={14} />
          </button>
        )}
      </td>
      <td className="tab-num tab-importo">{euro(riga.importo)}</td>
    </tr>
  );

  return (
    <div className="tab-page">
      <header className="tab-header">
        <div>
          <h1>Ordine Tabacchi</h1>
          <p className="tab-sub">
            {preordine?.ultimo_giorno_chiuso
              ? `Dati TabaUno alla chiusura del ${formattaChiusura(preordine.ultimo_giorno_chiuso)} · vendite delle ultime 4 settimane`
              : 'Dati TabaUno · vendite delle ultime 4 settimane'}
          </p>
          <p className={`tab-pc ${online ? 'online' : online === false ? 'offline' : ''}`}>
            PC negozio: {online == null ? '…' : online ? 'online' : 'offline'}
          </p>
        </div>
        <div className="tab-header-actions">
          {preordine && (
            <button
              type="button"
              className="tab-btn tab-btn-danger"
              onClick={() => elimina()}
              disabled={attesa}
            >
              <Trash2 size={15} />
              Elimina
            </button>
          )}
          <button
            type="button"
            className="tab-btn"
            onClick={() => (preordine ? elimina({ poiLeggi: true }) : leggi())}
            disabled={attesa || (!preordine && online !== true)}
          >
            {attesa ? 'Lettura…' : preordine ? 'Nuova lettura' : 'Leggi da PC'}
          </button>
        </div>
      </header>

      {errore && <div className="tab-error">{errore}</div>}

      {!preordine && !attesa && (
        <p className="tab-empty">Premi «Leggi da PC» quando il servizio TabaUnoAgent è online.</p>
      )}

      {preordine && (
        <>
          <div className="tab-controls">
            <div className="tab-control">
              <span className="tab-label">Copertura</span>
              <div className="tab-segments" role="group" aria-label="Giorni di copertura">
                {GIORNI.map(giorni => (
                  <button
                    key={giorni}
                    type="button"
                    className={preordine.giorni_copertura === giorni ? 'active' : ''}
                    disabled={!preordine.modificabile}
                    onClick={() => aggiornaParametri({ giorni_copertura: giorni })}
                  >
                    {giorni} gg
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
          </div>
          <p className="tab-hint">
            {fraseCopertura(preordine.giorni_alla_consegna, preordine.giorni_copertura, preordine.scorta_pct)}
          </p>

          <div className="tab-sezioni" role="tablist" aria-label="Tipo merce">
            {SEZIONI_ORDINE.map(item => {
              const stats = conteggi?.[item.id];
              return (
                <button
                  key={item.id}
                  type="button"
                  role="tab"
                  aria-selected={sezione === item.id}
                  className={`tab-sezione tab-sezione--${item.id}${sezione === item.id ? ' active' : ''}`}
                  onClick={() => { setSezione(item.id); setAltriAperti(false); setRicerca(''); }}
                >
                  <strong>{item.label}</strong>
                  <span>
                    {stats ? `${stats.articoli} da ordinare` : '—'}
                    {stats && stats.totali ? ` · ${stats.totali} in elenco` : ''}
                  </span>
                </button>
              );
            })}
          </div>

          {senzaLetturaDsp && (sezione === 'dispositivi' || sezione === 'solidi') && (
            <p className="tab-empty tab-empty-warn">
              In questa lettura non ci sono {sezione}. Aggiorna l’agente sul PC negozio (file tabacchi.py), riavvia TabaUnoAgent e fai «Nuova lettura».
            </p>
          )}

          <section className="tab-card">
            <div className="tab-card-head">
              <h2>Da ordinare · {SEZIONI_ORDINE.find(item => item.id === sezione)?.label}</h2>
              {sezioneMeta && (
                <span className="tab-card-meta">
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
                  <div className="tab-table-wrap">
                    <table className="tab-table">
                      <thead>
                        <tr>
                          <th>{etichettaSort('descrizione', 'Articolo')}</th>
                          <th>Giac.</th>
                          <th>Vende/gg</th>
                          <th>{etichettaSort('finisce', 'Finisce')}</th>
                          <th>{unitaLabel}</th>
                          <th>{etichettaSort('importo', 'Importo')}</th>
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
          </section>

          <section className="tab-card tab-others">
            <button type="button" className="tab-others-toggle" onClick={() => setAltriAperti(v => !v)}>
              {altriAperti ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
              <span>Altri articoli · {SEZIONI_ORDINE.find(item => item.id === sezione)?.label}</span>
              <em>{altriTotaliSezione} con scorta sufficiente · i primi finiscono prima</em>
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
                <div className="tab-table-wrap">
                  <table className="tab-table">
                    <thead>
                      <tr>
                        <th>{etichettaSort('descrizione', 'Articolo')}</th>
                        <th>Giac.</th>
                        <th>Vende/gg</th>
                        <th>{etichettaSort('finisce', 'Finisce')}</th>
                        <th></th>
                        <th>{etichettaSort('importo', 'Importo')}</th>
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

          <div className="tab-dock">
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
            <div className="tab-dock-actions">
              {haCorrezioni && (
                <button type="button" className="tab-btn ghost" onClick={annullaCorrezioni}>
                  Annulla correzioni
                </button>
              )}
              <button type="button" className="tab-btn ghost tab-btn-danger" onClick={() => elimina()} disabled={attesa}>
                <Trash2 size={14} />
                Elimina
              </button>
              <button type="button" className="tab-btn ghost" onClick={scaricaLogista}>
                Scarica Ordine_Logista.xls
              </button>
              <button type="button" className="tab-btn primary" onClick={copiaElenco}>
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
