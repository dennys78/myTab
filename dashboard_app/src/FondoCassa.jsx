import { useState, useEffect, useMemo } from 'react';
import { Plus, Trash2, Loader2, PiggyBank, Pencil, Check, X, TrendingUp, TrendingDown } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import { filterByPeriod } from './dateFilters';
import StoricoPeriodHeader from './StoricoPeriodHeader';

const TIPO_ENTRATA = 'ENTRATA';
const TIPO_USCITA = 'USCITA';

export default function FondoCassa() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'amministratore';

  const [movimenti, setMovimenti] = useState([]);
  const [totale, setTotale] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [tipo, setTipo] = useState(TIPO_ENTRATA);
  const [importo, setImporto] = useState('');
  const [descrizione, setDescrizione] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [storicoFiltro, setStoricoFiltro] = useState('week');

  const [editingId, setEditingId] = useState(null);
  const [editRow, setEditRow] = useState({});
  const [updating, setUpdating] = useState(false);

  const movimentiFiltrati = useMemo(
    () => filterByPeriod(movimenti, storicoFiltro),
    [movimenti, storicoFiltro],
  );

  const startEdit = (m) => {
    if (m.versamento_id) return;
    setEditingId(m.id);
    setEditRow({
      date: m.date,
      tipo: m.tipo || (m.importo >= 0 ? TIPO_ENTRATA : TIPO_USCITA),
      importo: Math.abs(Number(m.importo)),
      descrizione: m.descrizione || '',
    });
  };
  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const saveEdit = () => {
    setUpdating(true);
    apiFetch(`/api/fondo-cassa/${editingId}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: editRow.date,
        tipo: editRow.tipo,
        importo: parseFloat(editRow.importo) || 0,
        descrizione: editRow.descrizione,
      }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { cancelEdit(); fetchData(); } })
      .catch(() => {})
      .finally(() => setUpdating(false));
  };

  const fetchData = () => {
    setLoading(true);
    apiFetch('/api/fondo-cassa/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') { setMovimenti(d.data); setTotale(d.totale); }
        else setError(d.error || 'Errore caricamento');
      })
      .catch(() => setError('Errore di rete'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const handleSave = (e) => {
    e.preventDefault();
    const imp = parseFloat(importo);
    if (!imp || imp <= 0) { setSaveError('Inserisci un importo valido'); return; }
    setSaving(true);
    setSaveError(null);
    apiFetch('/api/fondo-cassa/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, tipo, importo: imp, descrizione }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImporto('');
          setDescrizione('');
          setTipo(TIPO_ENTRATA);
          fetchData();
        } else {
          setSaveError(d.error || 'Errore salvataggio');
        }
      })
      .catch(() => setSaveError('Errore di rete'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!window.confirm('Eliminare questo movimento?')) return;
    apiFetch(`/api/fondo-cassa/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchData(); })
      .catch(() => {});
  };

  const inp = (variant) => ({
    padding: '0.7rem 0.8rem',
    background: 'var(--bg-elevated)',
    border: `2px solid ${variant === 'entrata' ? 'rgba(34, 197, 94, 0.55)' : 'rgba(239, 68, 68, 0.55)'}`,
    color: 'white',
    borderRadius: '10px',
    fontSize: '0.95rem',
    boxSizing: 'border-box',
  });

  const resolveTipo = (m) => m.tipo || (Number(m.importo) >= 0 ? TIPO_ENTRATA : TIPO_USCITA);

  const formatImporto = (m, value) => {
    const t = isEditing(m) ? editRow.tipo : resolveTipo(m);
    const n = Number(value ?? m.importo).toFixed(2);
    return t === TIPO_ENTRATA ? `+ € ${n}` : `− € ${n}`;
  };

  const isEditing = (m) => editingId === m.id;

  return (
    <div style={{ maxWidth: '1120px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Fondo Cassa</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Accantonamenti e movimenti del fondo di riserva.
      </p>

      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px',
        padding: '1.25rem 1.5rem', marginBottom: '1.5rem',
        display: 'flex', alignItems: 'center', gap: '1rem',
      }}>
        <PiggyBank size={32} color="#f59e0b" style={{ flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Saldo Fondo Cassa</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: totale >= 0 ? '#f59e0b' : 'var(--danger)' }}>
            {totale === null ? '—' : `€ ${totale.toFixed(2)}`}
          </div>
        </div>
      </div>

      {isAdmin && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: '0 0 1.25rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={18} color="var(--accent)" /> Nuovo Movimento
          </h2>

          {saveError && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.65rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.875rem' }}>
              {saveError}
            </div>
          )}

          <form onSubmit={handleSave}>
            <div className="mov-form-tipo" role="group" aria-label="Tipo movimento">
              <button
                type="button"
                className={`mov-tipo-btn mov-tipo-btn--entrata ${tipo === TIPO_ENTRATA ? 'is-active' : ''}`}
                onClick={() => setTipo(TIPO_ENTRATA)}
              >
                <TrendingUp size={16} /> Entrata
              </button>
              <button
                type="button"
                className={`mov-tipo-btn mov-tipo-btn--uscita ${tipo === TIPO_USCITA ? 'is-active' : ''}`}
                onClick={() => setTipo(TIPO_USCITA)}
              >
                <TrendingDown size={16} /> Uscita
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem', marginBottom: '1rem', alignItems: 'end' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Data</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ ...inp(tipo === TIPO_ENTRATA ? 'entrata' : 'uscita'), width: '100%' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                  Importo (€) — {tipo === TIPO_ENTRATA ? 'entrata' : 'uscita'}
                </label>
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={importo}
                  onChange={e => setImporto(e.target.value)}
                  placeholder="0.00"
                  className={tipo === TIPO_ENTRATA ? 'mov-input-entrata' : 'mov-input-uscita'}
                  style={{ ...inp(tipo === TIPO_ENTRATA ? 'entrata' : 'uscita'), width: '100%' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '1rem' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Descrizione</label>
              <input
                type="text"
                value={descrizione}
                onChange={e => setDescrizione(e.target.value)}
                placeholder="es. Prelievo per spese..."
                style={{ ...inp('entrata'), width: '100%', borderColor: 'var(--border)' }}
              />
            </div>

            <button type="submit" disabled={saving || !importo} className="mov-submit-btn">
              {saving ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
              Registra Movimento
            </button>
          </form>
        </div>
      )}

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', overflow: 'hidden' }}>
        <StoricoPeriodHeader
          title="Storico Movimenti"
          value={storicoFiltro}
          onChange={setStoricoFiltro}
        />

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : error ? (
          <div style={{ padding: '1.5rem', color: 'var(--danger)', fontSize: '0.9rem' }}>{error}</div>
        ) : movimenti.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessun movimento registrato.</div>
        ) : movimentiFiltrati.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessun movimento nel periodo selezionato.</div>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="mov-table vers-table fondo-table">
              <thead>
                <tr>
                  {['Data', 'Tipo', 'Descrizione', 'Importo', ...(isAdmin ? ['Azioni'] : [])].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {movimentiFiltrati.map(m => {
                  const editing = isEditing(m);
                  const isEntrata = (editing ? editRow.tipo : resolveTipo(m)) === TIPO_ENTRATA;
                  const rowClass = isEntrata ? 'mov-row-entrata' : 'mov-row-uscita';
                  const fromVersamento = !!m.versamento_id;
                  const tdStyle = {};
                  const inpStyle = {
                    padding: '0.3rem 0.4rem',
                    background: 'var(--bg-dark)',
                    border: `2px solid ${isEntrata ? 'rgba(34, 197, 94, 0.55)' : 'rgba(239, 68, 68, 0.55)'}`,
                    color: 'white',
                    borderRadius: '5px',
                    fontSize: '0.85rem',
                  };
                  const displayImporto = Math.abs(Number(m.importo));
                  return (
                    <tr key={m.id} className={`${rowClass} ${editing ? 'vers-row-editing' : ''}`}>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                        {editing
                          ? <input type="date" value={editRow.date} onChange={e => setEditRow(r => ({ ...r, date: e.target.value }))} style={{ ...inpStyle, width: '130px' }} />
                          : new Date(`${m.date}T12:00:00`).toLocaleDateString('it-IT')}
                      </td>
                      <td style={tdStyle}>
                        {editing ? (
                          <select value={editRow.tipo} onChange={e => setEditRow(r => ({ ...r, tipo: e.target.value }))} style={{ ...inpStyle }}>
                            <option value={TIPO_ENTRATA}>Entrata</option>
                            <option value={TIPO_USCITA}>Uscita</option>
                          </select>
                        ) : (
                          <span className={isEntrata ? 'mov-badge-entrata' : 'mov-badge-uscita'}>
                            {isEntrata ? 'Entrata' : 'Uscita'}
                          </span>
                        )}
                      </td>
                      <td className="fondo-col-desc" style={{ ...tdStyle, color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        {editing
                          ? <input type="text" value={editRow.descrizione} onChange={e => setEditRow(r => ({ ...r, descrizione: e.target.value }))} style={{ ...inpStyle, width: '100%', minWidth: '180px' }} />
                          : (m.descrizione || (fromVersamento ? 'Accantonamento da versamento' : '—'))}
                      </td>
                      <td className="mov-importo-cell" style={tdStyle}>
                        {editing
                          ? <input type="number" min="0.01" step="0.01" value={editRow.importo} onChange={e => setEditRow(r => ({ ...r, importo: e.target.value }))} style={{ ...inpStyle, width: '100px' }} />
                          : <span className={isEntrata ? 'mov-importo-entrata' : 'mov-importo-uscita'}>{formatImporto(m, displayImporto)}</span>}
                      </td>
                      {isAdmin && (
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          {editing ? (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button onClick={saveEdit} disabled={updating} title="Salva" style={{ background: 'transparent', border: 'none', color: '#22c55e', cursor: 'pointer', padding: '0.25rem' }}>
                                {updating ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
                              </button>
                              <button onClick={cancelEdit} title="Annulla" style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.25rem' }}>
                                <X size={16} />
                              </button>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              {!fromVersamento && (
                                <button onClick={() => startEdit(m)} title="Modifica" style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: '0.25rem' }}>
                                  <Pencil size={15} />
                                </button>
                              )}
                              <button onClick={() => handleDelete(m.id)} title="Elimina" style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}>
                                <Trash2 size={15} />
                              </button>
                            </div>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
