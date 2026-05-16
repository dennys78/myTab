import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, PiggyBank, Pencil, Check, X } from 'lucide-react';
import { useAuth } from './AuthContext';

export default function FondoCassa() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'amministratore';

  const [movimenti, setMovimenti] = useState([]);
  const [totale, setTotale] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form (solo admin)
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [importo, setImporto] = useState('');
  const [descrizione, setDescrizione] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [filtro, setFiltro] = useState('mese');

  // Editing inline
  const [editingId, setEditingId] = useState(null);
  const [editRow, setEditRow] = useState({});
  const [updating, setUpdating] = useState(false);

  const startEdit = (m) => {
    setEditingId(m.id);
    setEditRow({ date: m.date, importo: m.importo, descrizione: m.descrizione });
  };
  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const saveEdit = () => {
    setUpdating(true);
    fetch(`/api/fondo-cassa/${editingId}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: editRow.date,
        importo: parseFloat(editRow.importo) || 0,
        descrizione: editRow.descrizione,
      }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { cancelEdit(); fetchData(); } })
      .catch(() => {})
      .finally(() => setUpdating(false));
  };

  const movimentiFiltrati = movimenti.filter(m => {
    if (filtro === 'tutti') return true;
    const data = new Date(m.date);
    const ora = new Date();
    if (filtro === 'mese') {
      return data.getFullYear() === ora.getFullYear() && data.getMonth() === ora.getMonth();
    }
    // tre mesi
    const treM = new Date(ora.getFullYear(), ora.getMonth() - 2, 1);
    return data >= treM;
  });

  const fetchData = () => {
    setLoading(true);
    fetch('/api/fondo-cassa/')
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
    if (imp === 0 || isNaN(imp)) { setSaveError('Inserisci un importo valido (positivo o negativo)'); return; }
    setSaving(true);
    setSaveError(null);
    fetch('/api/fondo-cassa/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, importo: imp, descrizione }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') { setImporto(''); setDescrizione(''); fetchData(); }
        else setSaveError(d.error || 'Errore salvataggio');
      })
      .catch(() => setSaveError('Errore di rete'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!window.confirm('Eliminare questo movimento?')) return;
    fetch(`/api/fondo-cassa/${id}/delete/`, { method: 'DELETE' })
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
    boxSizing: 'border-box',
  };

  return (
    <div style={{ maxWidth: '750px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Fondo Cassa</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Accantonamenti e movimenti del fondo di riserva.
      </p>

      {/* Totale */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px',
        padding: '1.25rem 1.5rem', marginBottom: '1.5rem',
        display: 'flex', alignItems: 'center', gap: '1rem',
      }}>
        <PiggyBank size={32} color="#f59e0b" style={{ flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Saldo Fondo Cassa</div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#f59e0b' }}>
            {totale === null ? '—' : `€ ${totale.toFixed(2)}`}
          </div>
        </div>
      </div>

      {/* Form nuovo movimento (solo admin) */}
      {isAdmin && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: '0 0 1.25rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Plus size={18} color="var(--accent)" /> Nuovo Movimento Manuale
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '1rem', marginTop: '-0.5rem' }}>
            Usa importi positivi per incrementare il fondo, negativi per prelevare.
          </p>

          {saveError && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.65rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.875rem' }}>
              {saveError}
            </div>
          )}

          <form onSubmit={handleSave}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Data</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ ...inp, width: '100%' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Importo (€)</label>
                <input type="number" step="0.01" value={importo} onChange={e => setImporto(e.target.value)}
                  placeholder="es. 50.00 o -20.00" style={{ ...inp, width: '100%' }} />
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Descrizione</label>
                <input type="text" value={descrizione} onChange={e => setDescrizione(e.target.value)}
                  placeholder="es. Prelievo per spese..." style={{ ...inp, width: '100%' }} />
              </div>
            </div>
            <button type="submit" disabled={saving || !importo}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                padding: '0.7rem 1.4rem',
                background: importo ? 'var(--accent)' : 'var(--bg-dark)',
                color: importo ? 'white' : 'var(--text-muted)',
                border: 'none', borderRadius: '8px',
                cursor: importo ? 'pointer' : 'not-allowed',
                fontWeight: 600, fontSize: '0.95rem',
              }}>
              {saving ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
              Aggiungi Movimento
            </button>
          </form>
        </div>
      )}

      {/* Storico movimenti */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
          <h2 style={{ margin: 0, fontSize: '1rem' }}>Storico Movimenti</h2>
          <select value={filtro} onChange={e => setFiltro(e.target.value)}
            style={{ padding: '0.4rem 0.75rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px', fontSize: '0.875rem', cursor: 'pointer' }}>
            <option value="mese">Mese corrente</option>
            <option value="tre">Tre mesi</option>
            <option value="tutti">Tutti</option>
          </select>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : error ? (
          <div style={{ padding: '1.5rem', color: 'var(--danger)', fontSize: '0.9rem' }}>{error}</div>
        ) : movimentiFiltrati.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            {movimenti.length === 0 ? 'Nessun movimento registrato.' : 'Nessun movimento nel periodo selezionato.'}
          </div>
        ) : (
          <div className="table-responsive-wrapper">
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Data', 'Descrizione', 'Importo', ...(isAdmin ? ['Azioni'] : [])].map(h => (
                    <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {movimentiFiltrati.map(m => {
                  const isEditing = editingId === m.id;
                  const tdStyle = { padding: '0.6rem 1rem', borderBottom: '1px solid var(--border)' };
                  const inpStyle = { padding: '0.35rem 0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--accent)', color: 'white', borderRadius: '5px', fontSize: '0.875rem' };
                  return (
                    <tr key={m.id}>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                        {isEditing
                          ? <input type="date" value={editRow.date} onChange={e => setEditRow(r => ({ ...r, date: e.target.value }))} style={{ ...inpStyle, width: '130px' }} />
                          : new Date(m.date).toLocaleDateString('it-IT')}
                      </td>
                      <td style={{ ...tdStyle, color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        {isEditing
                          ? <input type="text" value={editRow.descrizione} onChange={e => setEditRow(r => ({ ...r, descrizione: e.target.value }))} style={{ ...inpStyle, width: '100%', minWidth: '180px' }} />
                          : (m.descrizione || (m.versamento_id ? 'Accantonamento da versamento' : '—'))}
                      </td>
                      <td style={tdStyle}>
                        {isEditing
                          ? <input type="number" step="0.01" value={editRow.importo} onChange={e => setEditRow(r => ({ ...r, importo: e.target.value }))} style={{ ...inpStyle, width: '100px' }} />
                          : <span style={{ fontWeight: 700, color: m.importo >= 0 ? '#f59e0b' : 'var(--danger)' }}>
                              {m.importo >= 0 ? '+' : ''}€ {Number(m.importo).toFixed(2)}
                            </span>}
                      </td>
                      {isAdmin && (
                        <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                          {isEditing ? (
                            <div style={{ display: 'flex', gap: '0.4rem' }}>
                              <button onClick={saveEdit} disabled={updating}
                                title="Salva"
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
                              <button onClick={() => startEdit(m)} title="Modifica"
                                style={{ background: 'transparent', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: '0.25rem' }}>
                                <Pencil size={15} />
                              </button>
                              <button onClick={() => handleDelete(m.id)} title="Elimina"
                                style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}>
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
