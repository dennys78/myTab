import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Plus, Save, X, Trash2, Loader2, AlertCircle, Stamp, ChevronDown, ChevronRight, FileText, FileDown, Mail, Check,
} from 'lucide-react';
import { apiFetch } from './api';
import { ricevuteCardStyle, ricevuteInputStyle } from './ricevuteStyles';

const TIPO_VALORE_BOLLATO = 'valore_bollato';
const TIPO_CONTRIBUTO = 'contributo_unificato';

const todayIso = () => new Date().toISOString().slice(0, 10);

let lineUid = 0;
const newLineId = () => `line-${++lineUid}`;

const emptyLine = (tipo = TIPO_VALORE_BOLLATO) => ({
  _id: newLineId(),
  tipo,
  importo_unitario: '',
  quantita: 1,
});

const ARTICOLI_GRID = 'minmax(130px, 1fr) 100px 72px auto';

const iconActionStyle = (color, disabled = false) => ({
  background: 'transparent',
  border: `1px solid ${disabled ? 'var(--border)' : 'var(--border)'}`,
  borderRadius: '6px',
  padding: '0.4rem',
  cursor: disabled ? 'not-allowed' : 'pointer',
  color: disabled ? 'var(--text-muted)' : color,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  opacity: disabled ? 0.45 : 1,
});

function lineSubtotal(line) {
  const qty = Math.max(1, parseInt(line.quantita, 10) || 1);
  const unit = parseFloat(String(line.importo_unitario).replace(',', '.')) || 0;
  return Math.round(unit * qty * 100) / 100;
}

function buildLinePayload(line) {
  const qty = Math.max(1, parseInt(line.quantita, 10) || 1);
  const importo = parseFloat(String(line.importo_unitario).replace(',', '.')) || 0;
  if (importo <= 0) return null;
  if (line.tipo === TIPO_CONTRIBUTO) {
    return { tipo: TIPO_CONTRIBUTO, importo_unitario: importo, quantita: qty };
  }
  return { tipo: TIPO_VALORE_BOLLATO, importo_unitario: importo, quantita: qty };
}

export default function RicevuteValoriBollati() {
  const [clienti, setClienti] = useState([]);
  const [ricevute, setRicevute] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [detailCache, setDetailCache] = useState({});
  const [sendingEmailId, setSendingEmailId] = useState(null);
  const [emailSentMsg, setEmailSentMsg] = useState('');
  const [prossimoProgressivo, setProssimoProgressivo] = useState(1);
  const [numeroProgressivo, setNumeroProgressivo] = useState('1');
  const [savingProgressivoId, setSavingProgressivoId] = useState(null);
  const [progressivoEdits, setProgressivoEdits] = useState({});

  const [clienteId, setClienteId] = useState('');
  const [date, setDate] = useState(todayIso);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState([emptyLine()]);
  const lineValoreRefs = useRef({});
  const [focusLineId, setFocusLineId] = useState(null);

  const loadAll = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/api/ricevute/clienti/').then((r) => r.json()),
      apiFetch('/api/ricevute/emesse/').then((r) => r.json()),
    ])
      .then(([c, rec]) => {
        if (c.status === 'success') setClienti(c.data);
        if (rec.status === 'success') {
          setRicevute(rec.data);
          const next = rec.prossimo_progressivo ?? 1;
          setProssimoProgressivo(next);
          setNumeroProgressivo(String(next));
        }
        if (c.status !== 'success' || rec.status !== 'success') {
          setError('Errore caricamento dati ricevute.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadAll();
  }, []);

  useEffect(() => {
    if (!focusLineId) return;
    const el = lineValoreRefs.current[focusLineId];
    if (el) {
      el.focus();
      setFocusLineId(null);
    }
  }, [focusLineId, lines]);

  const totaleBozza = useMemo(
    () => lines.reduce((sum, line) => sum + lineSubtotal(line), 0),
    [lines],
  );

  const selectedCliente = clienti.find((c) => String(c.id) === String(clienteId));

  const updateLine = (lineId, patch) => {
    setLines((prev) => prev.map((line) => (line._id === lineId ? { ...line, ...patch } : line)));
  };

  const onTipoChange = (lineId, tipo) => {
    setLines((prev) => prev.map((line) => {
      if (line._id !== lineId) return line;
      if (tipo === TIPO_CONTRIBUTO) {
        return { ...line, tipo: TIPO_CONTRIBUTO };
      }
      return { ...line, tipo: TIPO_VALORE_BOLLATO };
    }));
  };

  const insertLineAfter = (afterId) => {
    const newLine = emptyLine();
    setLines((prev) => {
      const idx = prev.findIndex((l) => l._id === afterId);
      if (idx === -1) return [...prev, newLine];
      return [...prev.slice(0, idx + 1), newLine, ...prev.slice(idx + 1)];
    });
    setFocusLineId(newLine._id);
  };

  const removeLine = (lineId) => {
    setLines((prev) => (prev.length <= 1 ? prev : prev.filter((l) => l._id !== lineId)));
  };

  const resetForm = (nextProg = prossimoProgressivo) => {
    setClienteId('');
    setDate(todayIso());
    setNote('');
    setLines([emptyLine()]);
    setNumeroProgressivo(String(nextProg));
  };

  const handleSaveRicevuta = () => {
    if (!clienteId) {
      setError('Seleziona il cliente.');
      return;
    }
    const righe = lines
      .map((line) => buildLinePayload(line))
      .filter(Boolean);
    if (!righe.length) {
      setError('Aggiungi almeno un articolo valido.');
      return;
    }
    const prog = parseInt(String(numeroProgressivo).trim(), 10);
    if (!Number.isFinite(prog) || prog < 1) {
      setError('Inserisci un numero progressivo valido (≥ 1).');
      return;
    }
    setSaving(true);
    setError(null);
    apiFetch('/api/ricevute/emesse/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        cliente_id: Number(clienteId),
        date,
        note: note.trim(),
        righe,
        numero_progressivo: prog,
      }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          resetForm();
          loadAll();
        } else {
          setError(d.error || 'Errore salvataggio ricevuta.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const toggleDetail = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (detailCache[id]) return;
    apiFetch(`/api/ricevute/emesse/${id}/`)
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setDetailCache((prev) => ({ ...prev, [id]: d.data }));
          setProgressivoEdits((prev) => ({
            ...prev,
            [id]: String(d.data.numero_progressivo ?? ''),
          }));
        }
      })
      .catch(() => {});
  };

  const getProgressivoEdit = (row) => {
    if (progressivoEdits[row.id] !== undefined) return progressivoEdits[row.id];
    return String(row.numero_progressivo ?? '');
  };

  const handleSaveProgressivo = (row) => {
    const raw = String(getProgressivoEdit(row)).trim();
    const prog = parseInt(raw, 10);
    if (!Number.isFinite(prog) || prog < 1) {
      setError('Numero progressivo non valido.');
      return;
    }
    if (prog === row.numero_progressivo) return;

    setSavingProgressivoId(row.id);
    setError(null);
    apiFetch(`/api/ricevute/emesse/${row.id}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ numero_progressivo: prog }),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setDetailCache((prev) => ({ ...prev, [row.id]: d.data }));
          setProgressivoEdits((prev) => ({ ...prev, [row.id]: String(d.data.numero_progressivo) }));
          if (d.prossimo_progressivo != null) {
            setProssimoProgressivo(d.prossimo_progressivo);
            setNumeroProgressivo(String(d.prossimo_progressivo));
          }
          loadAll();
        } else {
          setError(d.error || 'Errore aggiornamento progressivo.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSavingProgressivoId(null));
  };

  const handleDeleteRicevuta = (row) => {
    if (!window.confirm(`Eliminare la ricevuta del ${row.date} per ${row.cliente?.ragione_sociale}?`)) return;
    apiFetch(`/api/ricevute/emesse/${row.id}/`, { method: 'DELETE' })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setExpandedId(null);
          loadAll();
        } else {
          setError(d.error || 'Errore eliminazione.');
        }
      })
      .catch(() => setError('Errore di rete.'));
  };

  const openPdf = (id) => {
    apiFetch(`/api/ricevute/emesse/${id}/pdf/`)
      .then((r) => {
        if (!r.ok) throw new Error('PDF non disponibile');
        return r.blob();
      })
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank', 'noopener,noreferrer');
        window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
      })
      .catch(() => setError('Impossibile generare il PDF.'));
  };

  const sendEmail = (row) => {
    if (!row?.cliente?.email) {
      setError('Il cliente non ha una email registrata.');
      return;
    }
    setSendingEmailId(row.id);
    setEmailSentMsg('');
    setError(null);
    apiFetch(`/api/ricevute/emesse/${row.id}/send-email/`, { method: 'POST' })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          const email = d.data?.email || row.cliente.email;
          const nProg = d.data?.numero_progressivo ?? row.numero_progressivo;
          const msg = d.message || `Email inviata con successo a ${email}.`;
          setEmailSentMsg(msg);
          window.alert(
            `Conferma invio\n\n${msg}\nRicevuta n. ${nProg}`,
          );
          setTimeout(() => setEmailSentMsg(''), 8000);
        } else {
          setError(d.error || 'Invio email non riuscito.');
        }
      })
      .catch(() => setError('Errore di rete durante invio email.'))
      .finally(() => setSendingEmailId(null));
  };

  const btnPrimary = {
    display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem',
    background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600,
  };

  return (
    <div style={{ maxWidth: '920px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Stamp size={26} color="var(--accent)" /> Ricevute valori bollati
      </h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Emetti ricevute per i clienti in archivio con il dettaglio delle marche da bollo e del contributo unificato.
      </p>

      {error && (
        <div style={{
          background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.75rem 1rem',
          borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem',
        }}>
          <AlertCircle size={18} /> {error}
          <button type="button" onClick={() => setError(null)} style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>
            <X size={16} />
          </button>
        </div>
      )}
      {emailSentMsg && (
        <div style={{
          background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.75rem 1rem',
          borderRadius: '8px', color: '#22c55e', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem',
        }}>
          <Check size={18} /> {emailSentMsg}
        </div>
      )}

      <div style={{ ...ricevuteCardStyle, marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 1rem', fontSize: '1.05rem' }}>Nuova ricevuta</h2>

        {clienti.length === 0 && !loading && (
          <p style={{ color: 'var(--warning, #f59e0b)', fontSize: '0.88rem', marginBottom: '1rem' }}>
            Nessun cliente in archivio. Aggiungili da <strong>Ricevute → Clienti</strong>.
          </p>
        )}

        <div style={{ display: 'grid', gap: '0.85rem', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Cliente *</label>
            <select
              style={ricevuteInputStyle}
              value={clienteId}
              onChange={(e) => setClienteId(e.target.value)}
            >
              <option value="">Seleziona cliente...</option>
              {clienti.map((c) => (
                <option key={c.id} value={c.id}>{c.ragione_sociale}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Data ricevuta</label>
            <input type="date" style={ricevuteInputStyle} value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>N. progressivo</label>
            <input
              type="number"
              min="1"
              step="1"
              style={ricevuteInputStyle}
              value={numeroProgressivo}
              onChange={(e) => setNumeroProgressivo(e.target.value)}
            />
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Prossimo suggerito: {prossimoProgressivo}. Puoi modificarlo prima del salvataggio.
            </p>
          </div>
        </div>

        {selectedCliente && (
          <div style={{
            marginBottom: '1.25rem', padding: '0.75rem 1rem', borderRadius: '8px',
            background: 'var(--bg-elevated)', border: '1px solid var(--border)', fontSize: '0.85rem',
          }}>
            <strong>{selectedCliente.ragione_sociale}</strong>
            {selectedCliente.indirizzo && <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>{selectedCliente.indirizzo}</div>}
            <div style={{ color: 'var(--text-muted)', marginTop: '0.25rem' }}>
              {selectedCliente.cf_piva && <>CF/PIVA: {selectedCliente.cf_piva}</>}
              {selectedCliente.email && <> · {selectedCliente.email}</>}
            </div>
          </div>
        )}

        <h3 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem' }}>Articoli</h3>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: ARTICOLI_GRID,
            gap: '0.65rem',
            alignItems: 'end',
            marginBottom: '0.5rem',
            padding: '0 0.85rem',
            fontSize: '0.72rem',
            fontWeight: 600,
            color: 'var(--text-muted)',
          }}
        >
          <span>Tipo</span>
          <span>Valore</span>
          <span>Qtà</span>
          <span style={{ textAlign: 'center' }}>Azioni</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1rem' }}>
          {lines.map((line) => (
            <div
              key={line._id}
              style={{
                padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
              }}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: ARTICOLI_GRID,
                  gap: '0.65rem',
                  alignItems: 'end',
                }}
              >
                <div>
                  <select
                    style={ricevuteInputStyle}
                    value={line.tipo}
                    onChange={(e) => onTipoChange(line._id, e.target.value)}
                  >
                    <option value={TIPO_VALORE_BOLLATO}>Valori bollati</option>
                    <option value={TIPO_CONTRIBUTO}>Contributo unificato</option>
                  </select>
                </div>

                <div>
                  <input
                    ref={(el) => { lineValoreRefs.current[line._id] = el; }}
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    style={ricevuteInputStyle}
                    value={line.importo_unitario}
                    onChange={(e) => updateLine(line._id, { importo_unitario: e.target.value })}
                  />
                </div>

                <div>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    style={ricevuteInputStyle}
                    value={line.quantita}
                    onChange={(e) => updateLine(line._id, { quantita: e.target.value })}
                  />
                </div>

                <div style={{ display: 'flex', gap: '0.35rem', justifyContent: 'center' }}>
                  <button
                    type="button"
                    title="Aggiungi riga sotto"
                    onClick={() => insertLineAfter(line._id)}
                    style={iconActionStyle('var(--accent)')}
                  >
                    <Plus size={16} />
                  </button>
                  <button
                    type="button"
                    title="Elimina riga"
                    onClick={() => removeLine(line._id)}
                    disabled={lines.length <= 1}
                    style={iconActionStyle('var(--danger)', lines.length <= 1)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.55rem', paddingTop: '0.45rem', borderTop: '1px dashed var(--border)' }}>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent)' }}>
                  € {lineSubtotal(line).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Note (opzionale)</label>
          <textarea style={{ ...ricevuteInputStyle, resize: 'vertical', minHeight: '2.5rem' }} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>

        <div style={{
          display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'flex-end', gap: '1rem',
          paddingTop: '1rem', borderTop: '1px solid var(--border)',
        }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" onClick={resetForm} style={{ ...btnPrimary, background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
              Annulla
            </button>
            <button type="button" onClick={handleSaveRicevuta} disabled={saving || !clienti.length} style={btnPrimary}>
              {saving ? <Loader2 size={18} className="spin" /> : <Save size={18} />}
              Salva ricevuta
            </button>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, marginLeft: 'auto' }}>
            Totale ricevuta: <span style={{ color: 'var(--accent)' }}>€ {totaleBozza.toFixed(2)}</span>
          </div>
        </div>
      </div>

      <div style={{ ...ricevuteCardStyle, marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 1rem', fontSize: '1.05rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <FileText size={20} /> Ricevute emesse
        </h2>
        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Caricamento...</p>
        ) : ricevute.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>Nessuna ricevuta salvata.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {ricevute.map((row) => {
              const open = expandedId === row.id;
              const detail = detailCache[row.id];
              return (
                <div key={row.id} style={{ border: '1px solid var(--border)', borderRadius: '10px', overflow: 'hidden' }}>
                  <button
                    type="button"
                    onClick={() => toggleDetail(row.id)}
                    style={{
                      width: '100%', textAlign: 'left', padding: '0.75rem 1rem', background: 'var(--bg-elevated)',
                      border: 'none', color: 'inherit', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem',
                    }}
                  >
                    {open ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    <span style={{ flex: 1 }}>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>n. {row.numero_progressivo}</span>
                      {' · '}
                      <strong>{new Date(row.date).toLocaleDateString('it-IT')}</strong>
                      {' — '}
                      {row.cliente?.ragione_sociale}
                    </span>
                    <span style={{ fontWeight: 700, color: 'var(--accent)' }}>€ {Number(row.totale).toFixed(2)}</span>
                  </button>
                  {open && detail && (
                    <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--border)' }}>
                      <div style={{
                        display: 'flex', flexWrap: 'wrap', alignItems: 'flex-end', gap: '0.65rem',
                        marginBottom: '1rem', padding: '0.75rem', borderRadius: '8px',
                        background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                      }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                            Numero progressivo
                          </label>
                          <input
                            type="number"
                            min="1"
                            step="1"
                            style={{ ...ricevuteInputStyle, width: '8rem' }}
                            value={getProgressivoEdit(row)}
                            onChange={(e) => setProgressivoEdits((prev) => ({ ...prev, [row.id]: e.target.value }))}
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => handleSaveProgressivo(row)}
                          disabled={
                            savingProgressivoId === row.id
                            || parseInt(getProgressivoEdit(row), 10) === row.numero_progressivo
                          }
                          style={{
                            ...btnPrimary,
                            padding: '0.5rem 0.9rem',
                            fontSize: '0.85rem',
                            opacity: parseInt(getProgressivoEdit(row), 10) === row.numero_progressivo ? 0.5 : 1,
                          }}
                        >
                          {savingProgressivoId === row.id ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
                          Salva progressivo
                        </button>
                      </div>
                      <table className="closures-table" style={{ marginBottom: '0.75rem' }}>
                        <thead>
                          <tr>
                            <th>Articolo</th>
                            <th>Descrizione</th>
                            <th style={{ textAlign: 'right' }}>Qtà</th>
                            <th style={{ textAlign: 'right' }}>Importo</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.righe.map((r) => (
                            <tr key={r.id}>
                              <td>{r.tipo_label}</td>
                              <td>{r.descrizione}</td>
                              <td style={{ textAlign: 'right' }}>{r.quantita}</td>
                              <td style={{ textAlign: 'right' }}>€ {Number(r.importo_totale).toFixed(2)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {detail.note && (
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: '0 0 0.75rem' }}>Note: {detail.note}</p>
                      )}
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => openPdf(row.id)}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', background: 'var(--accent)', border: 'none', color: '#fff', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
                        >
                          <FileDown size={15} /> Scarica PDF
                        </button>
                        <button
                          type="button"
                          onClick={() => sendEmail(row)}
                          disabled={sendingEmailId === row.id}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', background: 'rgba(79,141,247,0.15)', border: '1px solid var(--accent)', color: 'var(--accent)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem', opacity: sendingEmailId === row.id ? 0.7 : 1 }}
                        >
                          {sendingEmailId === row.id ? <Loader2 size={15} className="spin" /> : <Mail size={15} />}
                          Invia email
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteRicevuta(row)}
                          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', background: 'transparent', border: '1px solid var(--danger)', color: 'var(--danger)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
                        >
                          <Trash2 size={15} /> Elimina ricevuta
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
