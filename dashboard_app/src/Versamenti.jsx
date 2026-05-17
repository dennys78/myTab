import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, Wallet, ArrowDownToLine, Pencil, Check, X } from 'lucide-react';
import { useAuth } from './AuthContext';

export default function Versamenti() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'amministratore';

  const [versamenti, setVersamenti] = useState([]);
  const [saldoCassa, setSaldoCassa] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [importo, setImporto] = useState('');
  const [accantonamento, setAccantonamento] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const nettoAlBanco = Math.max(0, (parseFloat(importo) || 0) - (parseFloat(accantonamento) || 0));

  // Editing inline
  const [editingId, setEditingId] = useState(null);
  const [editRow, setEditRow] = useState({});
  const [updating, setUpdating] = useState(false);

  const startEdit = (v) => {
    setEditingId(v.id);
    setEditRow({ date: v.date, operator: v.operator, importo_versato: v.importo_versato, accantonamento: v.accantonamento });
  };
  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const saveEdit = () => {
    setUpdating(true);
    fetch(`/api/versamenti/${editingId}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: editRow.date,
        operator: editRow.operator,
        importo_versato: parseFloat(editRow.importo_versato) || 0,
        accantonamento: parseFloat(editRow.accantonamento) || 0,
      }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { cancelEdit(); fetchData(); } })
      .catch(() => {})
      .finally(() => setUpdating(false));
  };

  const fetchData = () => {
    setLoading(true);
    fetch('/api/versamenti/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setVersamenti(d.data);
          setSaldoCassa(d.saldo_cassa);
        } else {
          setError(d.error || 'Errore caricamento');
        }
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
    fetch('/api/versamenti/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        operator: user?.username || '',
        importo_versato: imp,
        accantonamento: parseFloat(accantonamento) || 0,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImporto('');
          setAccantonamento('');
          setDate(new Date().toISOString().split('T')[0]);
          fetchData();
        } else {
          setSaveError(d.error || 'Errore salvataggio');
        }
      })
      .catch(() => setSaveError('Errore di rete'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!window.confirm('Eliminare questo versamento?')) return;
    fetch(`/api/versamenti/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchData(); })
      .catch(() => {});
  };

  const inp = {
    padding: '0.65rem 0.75rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '8px',
    fontSize: '0.95rem',
  };

  return (
    <div style={{ maxWidth: '1050px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Versamenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Registra i versamenti di contanti effettuati in banca o in cassa.
      </p>

      {/* Saldo attuale */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
        padding: '1.25rem 1.5rem', marginBottom: '1.5rem',
        display: 'flex', alignItems: 'center', gap: '1rem',
      }}>
        <Wallet size={28} color="var(--accent)" style={{ flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
            Contanti in Cassa (disponibili)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: saldoCassa >= 0 ? '#22c55e' : 'var(--danger)' }}>
            {saldoCassa === null ? '—' : `€ ${saldoCassa.toFixed(2)}`}
          </div>
        </div>
      </div>

      {/* Form nuovo versamento */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 1.25rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ArrowDownToLine size={18} color="var(--accent)" /> Nuovo Versamento
        </h2>

        {saveError && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.65rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {saveError}
          </div>
        )}

        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            {/* Data */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Data</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
            </div>

            {/* Operatore (read-only) */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Operatore</label>
              <input type="text" value={user?.username || ''} readOnly
                style={{ ...inp, width: '100%', boxSizing: 'border-box', opacity: 0.6, cursor: 'default' }} />
            </div>

            {/* Importo */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Importo Prelevato (€)</label>
              <input type="number" min="0.01" step="0.01" value={importo}
                onChange={e => setImporto(e.target.value)}
                placeholder="0.00"
                style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
            </div>

            {/* Accantonamento */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Accantonamento Fondo (€)</label>
              <input type="number" min="0" step="0.01" value={accantonamento}
                onChange={e => setAccantonamento(e.target.value)}
                placeholder="0.00"
                style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
            </div>

            {/* Netto al banco (dinamico) */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Netto al Banco</label>
              <div style={{
                ...inp, display: 'flex', alignItems: 'center',
                fontWeight: 700, color: nettoAlBanco > 0 ? 'var(--accent)' : 'var(--text-muted)',
              }}>
                € {nettoAlBanco.toFixed(2)}
              </div>
            </div>

            {/* Saldo precedente (calcolato) */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Saldo Precedente</label>
              <div style={{
                ...inp, display: 'flex', alignItems: 'center',
                fontWeight: 700, opacity: 0.75,
                color: saldoCassa >= 0 ? '#22c55e' : 'var(--danger)',
              }}>
                {saldoCassa === null ? '—' : `€ ${saldoCassa.toFixed(2)}`}
              </div>
            </div>
          </div>

          <button type="submit" disabled={saving || !importo}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              padding: '0.7rem 1.4rem',
              background: importo ? 'var(--accent)' : 'var(--bg-dark)',
              color: importo ? 'white' : 'var(--text-muted)',
              border: 'none', borderRadius: '8px', cursor: importo ? 'pointer' : 'not-allowed',
              fontWeight: 600, fontSize: '0.95rem',
            }}>
            {saving ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
            Registra Versamento
          </button>
        </form>
      </div>

      {/* Storico versamenti */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ margin: 0, fontSize: '1rem' }}>Storico Versamenti</h2>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : error ? (
          <div style={{ padding: '1.5rem', color: 'var(--danger)', fontSize: '0.9rem' }}>{error}</div>
        ) : versamenti.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessun versamento registrato.</div>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="vers-table">
              <thead>
                <tr>
                  {['Data', 'Operatore', 'Saldo Prec.', 'Prelevato', 'Fondo', 'Netto Banco', 'Saldo Dopo', ...(isAdmin ? ['Azioni'] : [])].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versamenti.map(v => {
                  const isEditing = editingId === v.id;
                  const saldoDopo = v.saldo_precedente - v.importo_versato;
                  const netto = v.importo_versato - (v.accantonamento || 0);
                  const tdStyle = {};
                  const inpStyle = { padding: '0.3rem 0.4rem', background: 'var(--bg-dark)', border: '1px solid var(--accent)', color: 'white', borderRadius: '5px', fontSize: '0.85rem' };
                  return (
                    <tr key={v.id}>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                        {isEditing
                          ? <input type="date" value={editRow.date} onChange={e => setEditRow(r => ({ ...r, date: e.target.value }))} style={{ ...inpStyle, width: '130px' }} />
                          : new Date(v.date).toLocaleDateString('it-IT')}
                      </td>
                      <td style={tdStyle}>
                        {isEditing
                          ? <input type="text" value={editRow.operator} onChange={e => setEditRow(r => ({ ...r, operator: e.target.value }))} style={{ ...inpStyle, width: '110px' }} />
                          : v.operator}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: 600 }}>
                        € {v.saldo_precedente.toFixed(2)}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--danger)' }}>
                        {isEditing
                          ? <input type="number" min="0.01" step="0.01" value={editRow.importo_versato} onChange={e => setEditRow(r => ({ ...r, importo_versato: e.target.value }))} style={{ ...inpStyle, width: '90px' }} />
                          : `− € ${v.importo_versato.toFixed(2)}`}
                      </td>
                      <td style={{ ...tdStyle, color: v.accantonamento > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                        {isEditing
                          ? <input type="number" min="0" step="0.01" value={editRow.accantonamento} onChange={e => setEditRow(r => ({ ...r, accantonamento: e.target.value }))} style={{ ...inpStyle, width: '90px' }} />
                          : (v.accantonamento > 0 ? `€ ${v.accantonamento.toFixed(2)}` : '—')}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: 600, color: 'var(--accent)' }}>
                        € {netto.toFixed(2)}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: 700, color: saldoDopo >= 0 ? '#22c55e' : 'var(--danger)' }}>
                        € {saldoDopo.toFixed(2)}
                      </td>
                      {isAdmin && (
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          {isEditing ? (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button onClick={saveEdit} disabled={updating} title="Salva"
                                style={{ background: 'transparent', border: 'none', color: '#22c55e', cursor: 'pointer', padding: '0.25rem' }}>
                                {updating ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
                              </button>
                              <button onClick={cancelEdit} title="Annulla"
                                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '0.25rem' }}>
                                <X size={16} />
                              </button>
                            </div>
                          ) : (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button onClick={() => startEdit(v)} title="Modifica"
                                style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: '0.25rem' }}>
                                <Pencil size={15} />
                              </button>
                              <button onClick={() => handleDelete(v.id)} title="Elimina"
                                style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}>
                                <Trash2 size={16} />
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
