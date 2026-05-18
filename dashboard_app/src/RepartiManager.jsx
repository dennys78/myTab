import { useState, useEffect } from 'react';
import { Plus, Edit2, Save, X, Trash2, Loader2, AlertCircle, Tag } from 'lucide-react';
import { apiFetch } from './api';

export default function RepartiManager() {
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newName, setNewName] = useState('');
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState('');

  const fetchDepts = () => {
    apiFetch('/api/departments/')
      .then(r => r.json())
      .then(d => { if (d.status === 'success') setDepartments(d.data); })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchDepts(); }, []);

  const handleAdd = () => {
    const name = newName.trim();
    if (!name) return;
    setAdding(true);
    apiFetch('/api/departments/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { setNewName(''); fetchDepts(); } else setError(d.error); })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setAdding(false));
  };

  const handleSaveEdit = (id) => {
    const name = editName.trim();
    if (!name) return;
    apiFetch(`/api/departments/update/${id}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') { setEditingId(null); fetchDepts(); } else setError(d.error); })
      .catch(() => setError('Errore di rete.'));
  };

  const handleDelete = (id, name) => {
    if (!window.confirm(`Eliminare il reparto "${name}"?`)) return;
    apiFetch(`/api/departments/delete/${id}/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchDepts(); else setError(d.error); })
      .catch(() => setError('Errore di rete.'));
  };

  const inputStyle = {
    padding: '0.5rem 0.75rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.9rem',
  };

  const btnStyle = (variant = 'primary') => ({
    display: 'flex', alignItems: 'center', gap: '0.35rem',
    padding: '0.5rem 1rem',
    background: variant === 'primary' ? 'var(--accent)' : variant === 'danger' ? 'transparent' : 'transparent',
    color: variant === 'danger' ? 'var(--danger)' : variant === 'primary' ? 'white' : 'var(--accent)',
    border: variant === 'primary' ? 'none' : `1px solid ${variant === 'danger' ? 'var(--danger)' : 'var(--accent)'}`,
    borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: '600',
  });

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Gestione Reparti</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        I reparti vengono aggiunti automaticamente ad ogni acquisizione. Usa questa pagina solo per correggere nomi errati o rimuovere voci non valide.
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.75rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertCircle size={18} /> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 'auto', background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}><X size={16} /></button>
        </div>
      )}

      {/* Add row */}
      <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.5rem' }}>
        <input
          style={{ ...inputStyle, flex: 1 }}
          placeholder="Nome nuovo reparto (es. TABACCHI)"
          value={newName}
          onChange={e => setNewName(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAdd()}
        />
        <button onClick={handleAdd} disabled={adding || !newName.trim()} style={btnStyle()}>
          {adding ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
          Aggiungi
        </button>
      </div>

      {/* List */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento…</div>
        ) : departments.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            Nessun reparto. Aggiungine uno sopra.
          </div>
        ) : (
          departments.map((dept, i) => (
            <div
              key={dept.id}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.75rem',
                padding: '0.75rem 1rem',
                borderBottom: i < departments.length - 1 ? '1px solid var(--border)' : 'none',
              }}
            >
              <Tag size={16} color="var(--accent)" style={{ flexShrink: 0 }} />

              {editingId === dept.id ? (
                <>
                  <input
                    style={{ ...inputStyle, flex: 1 }}
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleSaveEdit(dept.id); if (e.key === 'Escape') setEditingId(null); }}
                    autoFocus
                  />
                  <button onClick={() => handleSaveEdit(dept.id)} style={btnStyle('secondary')}>
                    <Save size={15} /> Salva
                  </button>
                  <button onClick={() => setEditingId(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                    <X size={18} />
                  </button>
                </>
              ) : (
                <>
                  <span style={{ flex: 1, fontWeight: '500', letterSpacing: '0.02em' }}>{dept.name}</span>
                  <button onClick={() => { setEditingId(dept.id); setEditName(dept.name); }} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                    <Edit2 size={16} />
                  </button>
                  <button onClick={() => handleDelete(dept.id, dept.name)} style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>
                    <Trash2 size={16} />
                  </button>
                </>
              )}
            </div>
          ))
        )}
      </div>

      <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '1rem' }}>
        {departments.length} reparti in archivio
      </p>
    </div>
  );
}
