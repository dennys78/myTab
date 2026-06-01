import { useEffect, useMemo, useState } from 'react';
import {
  Plus, Save, X, Trash2, Loader2, AlertCircle, Stamp, ChevronDown, ChevronRight, FileText,
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
    return { tipo: TIPO_CONTRIBUTO, importo_unitario: importo, quantita: 1 };
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

  const [clienteId, setClienteId] = useState('');
  const [date, setDate] = useState(todayIso);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState([emptyLine()]);

  const loadAll = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/api/ricevute/clienti/').then((r) => r.json()),
      apiFetch('/api/ricevute/emesse/').then((r) => r.json()),
    ])
      .then(([c, rec]) => {
        if (c.status === 'success') setClienti(c.data);
        if (rec.status === 'success') setRicevute(rec.data);
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
        return { ...line, tipo: TIPO_CONTRIBUTO, quantita: 1 };
      }
      return { ...line, tipo: TIPO_VALORE_BOLLATO, quantita: 1 };
    }));
  };

  const addLine = () => {
    setLines((prev) => [...prev, emptyLine()]);
  };

  const removeLine = (lineId) => {
    setLines((prev) => (prev.length <= 1 ? prev : prev.filter((l) => l._id !== lineId)));
  };

  const resetForm = () => {
    setClienteId('');
    setDate(todayIso());
    setNote('');
    setLines([emptyLine()]);
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
        }
      })
      .catch(() => {});
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
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'flex-end',
                  gap: '0.65rem',
                }}
              >
                {lines.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeLine(line._id)}
                    title="Rimuovi riga"
                    style={{
                      flex: '0 0 auto', background: 'transparent', border: 'none', color: 'var(--danger)',
                      cursor: 'pointer', padding: '0.45rem 0', marginBottom: '0.1rem',
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                )}

                <div style={{ flex: '0 0 150px', minWidth: '130px' }}>
                  <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Tipo</label>
                  <select
                    style={ricevuteInputStyle}
                    value={line.tipo}
                    onChange={(e) => onTipoChange(line._id, e.target.value)}
                  >
                    <option value={TIPO_VALORE_BOLLATO}>Valori bollati</option>
                    <option value={TIPO_CONTRIBUTO}>Contributo unificato</option>
                  </select>
                </div>

                <div style={{ flex: '0 0 100px', minWidth: '88px' }}>
                  <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Valore</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    style={ricevuteInputStyle}
                    value={line.importo_unitario}
                    onChange={(e) => updateLine(line._id, { importo_unitario: e.target.value })}
                  />
                </div>

                {line.tipo === TIPO_VALORE_BOLLATO && (
                  <div style={{ flex: '0 0 72px', minWidth: '64px' }}>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Qtà</label>
                    <input
                      type="number"
                      min="1"
                      step="1"
                      style={ricevuteInputStyle}
                      value={line.quantita}
                      onChange={(e) => updateLine(line._id, { quantita: e.target.value })}
                    />
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '0.55rem', paddingTop: '0.45rem', borderTop: '1px dashed var(--border)' }}>
                <span style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--accent)' }}>
                  € {lineSubtotal(line).toFixed(2)}
                </span>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          <button type="button" onClick={addLine} style={{ ...btnPrimary, background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)' }}>
            <Plus size={16} /> Aggiungi
          </button>
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
                      <strong>{new Date(row.date).toLocaleDateString('it-IT')}</strong>
                      {' — '}
                      {row.cliente?.ragione_sociale}
                    </span>
                    <span style={{ fontWeight: 700, color: 'var(--accent)' }}>€ {Number(row.totale).toFixed(2)}</span>
                  </button>
                  {open && detail && (
                    <div style={{ padding: '0.75rem 1rem', borderTop: '1px solid var(--border)' }}>
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
                      <button
                        type="button"
                        onClick={() => handleDeleteRicevuta(row)}
                        style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.45rem 0.8rem', background: 'transparent', border: '1px solid var(--danger)', color: 'var(--danger)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}
                      >
                        <Trash2 size={15} /> Elimina ricevuta
                      </button>
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
