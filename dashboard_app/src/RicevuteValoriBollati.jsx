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
  valore_bollato_id: '',
  descrizione: '',
  importo_unitario: '',
  quantita: 1,
});

function lineSubtotal(line) {
  const qty = Math.max(1, parseInt(line.quantita, 10) || 1);
  const unit = parseFloat(String(line.importo_unitario).replace(',', '.')) || 0;
  return Math.round(unit * qty * 100) / 100;
}

function buildLinePayload(line, catalog) {
  const qty = Math.max(1, parseInt(line.quantita, 10) || 1);
  if (line.tipo === TIPO_CONTRIBUTO) {
    return {
      tipo: TIPO_CONTRIBUTO,
      importo_unitario: parseFloat(String(line.importo_unitario).replace(',', '.')) || 0,
      quantita: qty,
    };
  }
  if (line.valore_bollato_id) {
    return { tipo: TIPO_VALORE_BOLLATO, valore_bollato_id: Number(line.valore_bollato_id), quantita: qty };
  }
  const preset = catalog.find((v) => String(v.id) === String(line.valore_bollato_id));
  return {
    tipo: TIPO_VALORE_BOLLATO,
    descrizione: line.descrizione.trim() || preset?.descrizione || '',
    importo_unitario: parseFloat(String(line.importo_unitario).replace(',', '.')) || preset?.importo || 0,
    quantita: qty,
  };
}

export default function RicevuteValoriBollati() {
  const [clienti, setClienti] = useState([]);
  const [catalogo, setCatalogo] = useState([]);
  const [ricevute, setRicevute] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [detailCache, setDetailCache] = useState({});

  const [clienteId, setClienteId] = useState('');
  const [date, setDate] = useState(todayIso);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState([emptyLine()]);

  const [catForm, setCatForm] = useState({ descrizione: '', importo: '' });
  const [catSaving, setCatSaving] = useState(false);

  const loadAll = () => {
    setLoading(true);
    setError(null);
    Promise.all([
      apiFetch('/api/ricevute/clienti/').then((r) => r.json()),
      apiFetch('/api/ricevute/valori-bollati/').then((r) => r.json()),
      apiFetch('/api/ricevute/emesse/').then((r) => r.json()),
    ])
      .then(([c, cat, rec]) => {
        if (c.status === 'success') setClienti(c.data);
        if (cat.status === 'success') setCatalogo(cat.data);
        if (rec.status === 'success') setRicevute(rec.data);
        if (c.status !== 'success' || cat.status !== 'success' || rec.status !== 'success') {
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

  const onCatalogPick = (lineId, valoreId) => {
    const item = catalogo.find((v) => String(v.id) === String(valoreId));
    updateLine(lineId, {
      valore_bollato_id: valoreId,
      descrizione: item?.descrizione || '',
      importo_unitario: item ? String(item.importo) : '',
    });
  };

  const onTipoChange = (lineId, tipo) => {
    setLines((prev) => prev.map((line) => {
      if (line._id !== lineId) return line;
      if (tipo === TIPO_CONTRIBUTO) {
        return {
          ...line,
          tipo: TIPO_CONTRIBUTO,
          valore_bollato_id: '',
          descrizione: 'Contributo unificato',
          quantita: 1,
        };
      }
      return {
        ...line,
        tipo: TIPO_VALORE_BOLLATO,
        valore_bollato_id: '',
        descrizione: '',
        importo_unitario: '',
        quantita: 1,
      };
    }));
  };

  const addLine = (tipo) => {
    setLines((prev) => [...prev, emptyLine(tipo)]);
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
      .map((line) => buildLinePayload(line, catalogo))
      .filter((r) => {
        if (r.tipo === TIPO_CONTRIBUTO) return r.importo_unitario > 0;
        return r.valore_bollato_id || (r.descrizione && r.importo_unitario > 0);
      });
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

  const handleAddCatalogItem = () => {
    if (!catForm.descrizione.trim()) {
      setError('Inserisci la descrizione della marca da bollo.');
      return;
    }
    setCatSaving(true);
    apiFetch('/api/ricevute/valori-bollati/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(catForm),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setCatForm({ descrizione: '', importo: '' });
          loadAll();
        } else {
          setError(d.error || 'Errore catalogo.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setCatSaving(false));
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
          {lines.map((line, index) => (
            <div
              key={line._id}
              style={{
                padding: '0.85rem', borderRadius: '10px', border: '1px solid var(--border)',
                background: 'var(--bg-elevated)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem', gap: '0.5rem' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Riga {index + 1}</span>
                {lines.length > 1 && (
                  <button type="button" onClick={() => removeLine(line._id)} style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: 0 }}>
                    <Trash2 size={16} />
                  </button>
                )}
              </div>

              <div style={{ display: 'grid', gap: '0.65rem', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))' }}>
                <div>
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

                {line.tipo === TIPO_VALORE_BOLLATO ? (
                  <>
                    <div style={{ gridColumn: 'span 2' }}>
                      <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Marca da bollo</label>
                      <select
                        style={ricevuteInputStyle}
                        value={line.valore_bollato_id}
                        onChange={(e) => onCatalogPick(line._id, e.target.value)}
                      >
                        <option value="">Seleziona dal catalogo...</option>
                        {catalogo.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.descrizione} — € {Number(v.importo).toFixed(2)}
                          </option>
                        ))}
                      </select>
                    </div>
                    {!line.valore_bollato_id && (
                      <>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Descrizione</label>
                          <input style={ricevuteInputStyle} value={line.descrizione} onChange={(e) => updateLine(line._id, { descrizione: e.target.value })} placeholder="Descrizione" />
                        </div>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Importo €</label>
                          <input type="number" min="0" step="0.01" style={ricevuteInputStyle} value={line.importo_unitario} onChange={(e) => updateLine(line._id, { importo_unitario: e.target.value })} />
                        </div>
                      </>
                    )}
                  </>
                ) : (
                  <div>
                    <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Importo contributo €</label>
                    <input type="number" min="0" step="0.01" style={ricevuteInputStyle} value={line.importo_unitario} onChange={(e) => updateLine(line._id, { importo_unitario: e.target.value })} />
                  </div>
                )}

                <div>
                  <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>Quantità</label>
                  <input
                    type="number"
                    min="1"
                    step="1"
                    style={ricevuteInputStyle}
                    value={line.quantita}
                    onChange={(e) => updateLine(line._id, { quantita: e.target.value })}
                    disabled={line.tipo === TIPO_CONTRIBUTO}
                  />
                </div>

                <div style={{ display: 'flex', alignItems: 'flex-end' }}>
                  <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent)' }}>
                    € {lineSubtotal(line).toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
          <button type="button" onClick={() => addLine(TIPO_VALORE_BOLLATO)} style={{ ...btnPrimary, background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)' }}>
            <Plus size={16} /> Valore bollato
          </button>
          <button type="button" onClick={() => addLine(TIPO_CONTRIBUTO)} style={{ ...btnPrimary, background: 'transparent', color: 'var(--accent)', border: '1px solid var(--accent)' }}>
            <Plus size={16} /> Contributo unificato
          </button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Note (opzionale)</label>
          <textarea style={{ ...ricevuteInputStyle, resize: 'vertical', minHeight: '2.5rem' }} rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
        </div>

        <div style={{
          display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem',
          paddingTop: '1rem', borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: '1.15rem', fontWeight: 700 }}>
            Totale ricevuta: <span style={{ color: 'var(--accent)' }}>€ {totaleBozza.toFixed(2)}</span>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button type="button" onClick={resetForm} style={{ ...btnPrimary, background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)' }}>
              Annulla
            </button>
            <button type="button" onClick={handleSaveRicevuta} disabled={saving || !clienti.length} style={btnPrimary}>
              {saving ? <Loader2 size={18} className="spin" /> : <Save size={18} />}
              Salva ricevuta
            </button>
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

      <div style={ricevuteCardStyle}>
        <button
          type="button"
          onClick={() => setCatalogOpen((o) => !o)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'transparent',
            border: 'none', color: 'var(--text-main)', cursor: 'pointer', padding: 0, fontWeight: 600, fontSize: '0.95rem',
          }}
        >
          {catalogOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
          Catalogo marche da bollo
        </button>
        {catalogOpen && (
          <div style={{ marginTop: '1rem' }}>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
              Voci predefinite selezionabili nelle righe &quot;Valori bollati&quot;.
            </p>
            <div style={{ display: 'grid', gap: '0.65rem', gridTemplateColumns: '1fr 120px auto', marginBottom: '1rem' }}>
              <input style={ricevuteInputStyle} placeholder="Descrizione" value={catForm.descrizione} onChange={(e) => setCatForm({ ...catForm, descrizione: e.target.value })} />
              <input type="number" min="0" step="0.01" style={ricevuteInputStyle} placeholder="€" value={catForm.importo} onChange={(e) => setCatForm({ ...catForm, importo: e.target.value })} />
              <button type="button" onClick={handleAddCatalogItem} disabled={catSaving} style={btnPrimary}>
                {catSaving ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
              </button>
            </div>
            {catalogo.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Catalogo vuoto: aggiungi le marche più usate.</p>
            ) : (
              <ul style={{ margin: 0, padding: 0, listStyle: 'none' }}>
                {catalogo.map((v) => (
                  <li key={v.id} style={{ padding: '0.45rem 0', borderBottom: '1px solid var(--border)', fontSize: '0.9rem' }}>
                    {v.descrizione} — <strong>€ {Number(v.importo).toFixed(2)}</strong>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
