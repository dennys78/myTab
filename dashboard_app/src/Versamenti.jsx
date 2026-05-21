import { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, Wallet, ArrowDownToLine, Pencil, Check, X, Bookmark } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';

export default function Versamenti({ initialEditId = null, onEditConsumed }) {
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
  const [note, setNote] = useState('');
  const [ricordaPromemoria, setRicordaPromemoria] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Editing inline
  const [editingId, setEditingId] = useState(null);
  const [editRow, setEditRow] = useState({});
  const [updating, setUpdating] = useState(false);

  const startEdit = (v) => {
    setEditingId(v.id);
    setEditRow({
      date: v.date,
      importo_versato: v.importo_versato,
      accantonamento: v.accantonamento,
      note: v.note || '',
      ricorda_promemoria: !!v.ricorda_promemoria,
    });
  };
  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const saveEdit = () => {
    setUpdating(true);
    apiFetch(`/api/versamenti/${editingId}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: editRow.date,
        importo_versato: parseFloat(editRow.importo_versato) || 0,
        accantonamento: parseFloat(editRow.accantonamento) || 0,
        note: editRow.note || '',
        ricorda_promemoria: !!editRow.ricorda_promemoria,
      }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { cancelEdit(); fetchData(); } })
      .catch(() => {})
      .finally(() => setUpdating(false));
  };

  const fetchData = () => {
    setLoading(true);
    apiFetch('/api/versamenti/')
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

  useEffect(() => {
    if (!initialEditId || loading || versamenti.length === 0) return;
    const target = versamenti.find(v => v.id === initialEditId);
    if (!target) return;
    startEdit(target);
    onEditConsumed?.();
    const t = window.setTimeout(() => {
      document.getElementById(`vers-row-${target.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
    return () => window.clearTimeout(t);
  }, [initialEditId, loading, versamenti]);

  const handleSave = (e) => {
    e.preventDefault();
    const imp = parseFloat(importo);
    if (!imp || imp <= 0) { setSaveError('Inserisci un importo valido'); return; }
    setSaving(true);
    setSaveError(null);
    apiFetch('/api/versamenti/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        operator: user?.username || '',
        importo_versato: imp,
        accantonamento: parseFloat(accantonamento) || 0,
        note,
        ricorda_promemoria: ricordaPromemoria,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImporto('');
          setAccantonamento('');
          setNote('');
          setRicordaPromemoria(false);
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
    apiFetch(`/api/versamenti/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchData(); })
      .catch(() => {});
  };

  const inp = {
    padding: '0.7rem 0.8rem',
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '10px',
    fontSize: '0.95rem',
  };

  return (
    <div style={{ maxWidth: '1120px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Versamenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Registra i versamenti di contanti effettuati in banca o in cassa.
      </p>

      {/* Saldo attuale */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px',
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
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 1.25rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ArrowDownToLine size={18} color="var(--accent)" /> Nuovo Versamento
        </h2>

        {saveError && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.65rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.875rem' }}>
            {saveError}
          </div>
        )}

        <form onSubmit={handleSave}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginTop: '-0.5rem', marginBottom: '1rem' }}>
            Compila solo i campi operativi: l'operatore viene registrato automaticamente in base all'utente connesso.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: '1rem', marginBottom: '1rem', alignItems: 'end' }}>
            {/* Data */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Data</label>
              <input type="date" value={date} onChange={e => setDate(e.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
            </div>

            {/* Importo */}
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-main)', marginBottom: '0.35rem', fontWeight: 700 }}>Totale versato (€)</label>
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
          </div>

          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Note</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Aggiungi eventuali note sul versamento..."
              rows={3}
              style={{ ...inp, width: '100%', boxSizing: 'border-box', resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.45 }}
            />
          </div>

          <label className="vers-promemoria-flag">
            <input
              type="checkbox"
              checked={ricordaPromemoria}
              onChange={e => setRicordaPromemoria(e.target.checked)}
            />
            <Bookmark size={16} />
            <span>Ricorda come promemoria</span>
          </label>
          <p className="vers-promemoria-hint">
            Se attivo, il versamento compare nei promemoria in dashboard (puoi averne più di uno).
          </p>

          <button type="submit" disabled={saving || !importo}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
                padding: '0.75rem 1.4rem',
              background: importo ? 'var(--accent)' : 'var(--bg-dark)',
              color: importo ? 'white' : 'var(--text-muted)',
                border: 'none', borderRadius: '10px', cursor: importo ? 'pointer' : 'not-allowed',
              fontWeight: 600, fontSize: '0.95rem',
            }}>
            {saving ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
            Registra Versamento
          </button>
        </form>
      </div>

      {/* Storico versamenti */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', overflow: 'hidden' }}>
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
                  {['Data', 'Operatore', 'Totale versato', 'Fondo', 'Note', ...(isAdmin ? ['Azioni'] : [])].map(h => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versamenti.map(v => {
                  const isEditing = editingId === v.id;
                  const tdStyle = {};
                  const inpStyle = { padding: '0.3rem 0.4rem', background: 'var(--bg-dark)', border: '1px solid var(--accent)', color: 'white', borderRadius: '5px', fontSize: '0.85rem' };
                  return (
                    <tr key={v.id} id={`vers-row-${v.id}`} className={editingId === v.id ? 'vers-row-editing' : ''}>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>
                        {isEditing
                          ? <input type="date" value={editRow.date} onChange={e => setEditRow(r => ({ ...r, date: e.target.value }))} style={{ ...inpStyle, width: '130px' }} />
                          : new Date(v.date).toLocaleDateString('it-IT')}
                      </td>
                      <td style={tdStyle}>
                        {v.operator}
                      </td>
                      <td style={{ ...tdStyle, fontWeight: 700, color: 'var(--danger)' }}>
                        {isEditing
                          ? <input type="number" min="0.01" step="0.01" value={editRow.importo_versato} onChange={e => setEditRow(r => ({ ...r, importo_versato: e.target.value }))} style={{ ...inpStyle, width: '90px' }} />
                          : `€ ${v.importo_versato.toFixed(2)}`}
                      </td>
                      <td style={{ ...tdStyle, color: v.accantonamento > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
                        {isEditing
                          ? <input type="number" min="0" step="0.01" value={editRow.accantonamento} onChange={e => setEditRow(r => ({ ...r, accantonamento: e.target.value }))} style={{ ...inpStyle, width: '90px' }} />
                          : (v.accantonamento > 0 ? `€ ${v.accantonamento.toFixed(2)}` : '—')}
                      </td>
                      <td style={{ ...tdStyle, minWidth: '180px', color: 'var(--text-muted)' }}>
                        {isEditing ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                            <textarea value={editRow.note} onChange={e => setEditRow(r => ({ ...r, note: e.target.value }))} rows={2} style={{ ...inpStyle, width: '100%', minWidth: '180px', resize: 'vertical', fontFamily: 'inherit' }} />
                            <label className="vers-promemoria-flag vers-promemoria-flag--compact">
                              <input
                                type="checkbox"
                                checked={!!editRow.ricorda_promemoria}
                                onChange={e => setEditRow(r => ({ ...r, ricorda_promemoria: e.target.checked }))}
                              />
                              <Bookmark size={14} />
                              <span>Promemoria</span>
                            </label>
                          </div>
                        ) : (
                          <div>
                            {v.ricorda_promemoria && (
                              <div className="vers-promemoria-badge" title="Promemoria in dashboard">
                                <Bookmark size={12} /> Promemoria
                              </div>
                            )}
                            <span>{v.note || '—'}</span>
                          </div>
                        )}
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
