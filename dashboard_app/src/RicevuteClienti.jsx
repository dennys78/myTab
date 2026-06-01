import { useEffect, useState } from 'react';
import { Plus, Edit2, Save, X, Trash2, Loader2, AlertCircle, Users } from 'lucide-react';
import { apiFetch } from './api';
import { ricevuteCardStyle, ricevuteInputStyle } from './ricevuteStyles';

const emptyForm = () => ({
  ragione_sociale: '',
  indirizzo: '',
  cf_piva: '',
  email: '',
});

export default function RicevuteClienti() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  const fetchRows = () => {
    apiFetch('/api/ricevute/clienti/')
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') setRows(d.data);
        else setError(d.error || 'Errore caricamento clienti.');
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRows();
  }, []);

  const handleCreate = () => {
    if (!form.ragione_sociale.trim()) {
      setError('La ragione sociale è obbligatoria.');
      return;
    }
    setSaving(true);
    setError(null);
    apiFetch('/api/ricevute/clienti/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setForm(emptyForm());
          fetchRows();
        } else {
          setError(d.error || 'Errore salvataggio.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const startEdit = (row) => {
    setEditingId(row.id);
    setEditForm({
      ragione_sociale: row.ragione_sociale || '',
      indirizzo: row.indirizzo || '',
      cf_piva: row.cf_piva || '',
      email: row.email || '',
    });
  };

  const handleSaveEdit = () => {
    if (!editForm.ragione_sociale.trim()) {
      setError('La ragione sociale è obbligatoria.');
      return;
    }
    setSaving(true);
    setError(null);
    apiFetch(`/api/ricevute/clienti/${editingId}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm),
    })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') {
          setEditingId(null);
          fetchRows();
        } else {
          setError(d.error || 'Errore aggiornamento.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (row) => {
    if (!window.confirm(`Eliminare il cliente "${row.ragione_sociale}"?`)) return;
    apiFetch(`/api/ricevute/clienti/${row.id}/`, { method: 'DELETE' })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') fetchRows();
        else setError(d.error || 'Errore eliminazione.');
      })
      .catch(() => setError('Errore di rete.'));
  };

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Users size={26} color="var(--accent)" /> Clienti
      </h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Anagrafica clienti per l&apos;emissione delle ricevute.
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
        <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Nuovo cliente</h2>
        <div style={{ display: 'grid', gap: '0.75rem', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Ragione sociale *</label>
            <input style={ricevuteInputStyle} value={form.ragione_sociale} onChange={(e) => setForm({ ...form, ragione_sociale: e.target.value })} placeholder="es. Rossi Mario S.r.l." />
          </div>
          <div style={{ gridColumn: '1 / -1' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Indirizzo</label>
            <textarea style={{ ...ricevuteInputStyle, resize: 'vertical', minHeight: '2.5rem' }} rows={2} value={form.indirizzo} onChange={(e) => setForm({ ...form, indirizzo: e.target.value })} placeholder="Via, CAP, Città" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>CF/PIVA</label>
            <input style={ricevuteInputStyle} value={form.cf_piva} onChange={(e) => setForm({ ...form, cf_piva: e.target.value })} placeholder="IT12345678901" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Email</label>
            <input type="email" style={ricevuteInputStyle} value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="cliente@email.it" />
          </div>
        </div>
        <button
          type="button"
          onClick={handleCreate}
          disabled={saving}
          style={{
            marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem',
            background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600,
          }}
        >
          {saving ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
          Aggiungi cliente
        </button>
      </div>

      <div style={ricevuteCardStyle}>
        <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Elenco clienti ({rows.length})</h2>
        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Caricamento...</p>
        ) : rows.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>Nessun cliente registrato.</p>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="closures-table">
              <thead>
                <tr>
                  <th>Ragione sociale</th>
                  <th>Indirizzo</th>
                  <th>CF/PIVA</th>
                  <th>Email</th>
                  <th style={{ width: '120px' }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    {editingId === row.id ? (
                      <>
                        <td><input style={ricevuteInputStyle} value={editForm.ragione_sociale} onChange={(e) => setEditForm({ ...editForm, ragione_sociale: e.target.value })} /></td>
                        <td><input style={ricevuteInputStyle} value={editForm.indirizzo} onChange={(e) => setEditForm({ ...editForm, indirizzo: e.target.value })} /></td>
                        <td><input style={ricevuteInputStyle} value={editForm.cf_piva} onChange={(e) => setEditForm({ ...editForm, cf_piva: e.target.value })} /></td>
                        <td><input style={ricevuteInputStyle} value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button type="button" onClick={handleSaveEdit} disabled={saving} style={{ background: 'var(--accent)', border: 'none', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'white' }}><Save size={16} /></button>
                            <button type="button" onClick={() => setEditingId(null)} style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={16} /></button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td style={{ fontWeight: 600 }}>{row.ragione_sociale}</td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.88rem' }}>{row.indirizzo || '—'}</td>
                        <td>{row.cf_piva || '—'}</td>
                        <td>{row.email ? <a href={`mailto:${row.email}`} style={{ color: 'var(--accent)' }}>{row.email}</a> : '—'}</td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button type="button" onClick={() => startEdit(row)} style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'var(--accent)' }}><Edit2 size={16} /></button>
                            <button type="button" onClick={() => handleDelete(row)} style={{ background: 'transparent', border: '1px solid var(--danger)', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'var(--danger)' }}><Trash2 size={16} /></button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
