import { useEffect, useState } from 'react';
import { Plus, Edit2, Save, X, Trash2, Loader2, AlertCircle, Stamp } from 'lucide-react';
import { apiFetch } from './api';
import { ricevuteCardStyle, ricevuteInputStyle } from './ricevuteStyles';

const emptyForm = () => ({ descrizione: '', importo: '' });

export default function RicevuteValoriBollati() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState(emptyForm);

  const fetchRows = () => {
    apiFetch('/api/ricevute/valori-bollati/')
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') setRows(d.data);
        else setError(d.error || 'Errore caricamento valori bollati.');
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRows();
  }, []);

  const handleCreate = () => {
    if (!form.descrizione.trim()) {
      setError('La descrizione è obbligatoria.');
      return;
    }
    setSaving(true);
    setError(null);
    apiFetch('/api/ricevute/valori-bollati/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ descrizione: form.descrizione, importo: form.importo || 0 }),
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
    setEditForm({ descrizione: row.descrizione || '', importo: String(row.importo ?? '') });
  };

  const handleSaveEdit = () => {
    if (!editForm.descrizione.trim()) {
      setError('La descrizione è obbligatoria.');
      return;
    }
    setSaving(true);
    setError(null);
    apiFetch(`/api/ricevute/valori-bollati/${editingId}/`, {
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
    if (!window.confirm(`Eliminare "${row.descrizione}"?`)) return;
    apiFetch(`/api/ricevute/valori-bollati/${row.id}/`, { method: 'DELETE' })
      .then((r) => r.json())
      .then((d) => {
        if (d.status === 'success') fetchRows();
        else setError(d.error || 'Errore eliminazione.');
      })
      .catch(() => setError('Errore di rete.'));
  };

  return (
    <div style={{ maxWidth: '720px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Stamp size={26} color="var(--accent)" /> Valori bollati
      </h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
        Elenco dei valori bollati con importo di riferimento per le ricevute.
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
        <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Nuovo valore bollato</h2>
        <div style={{ display: 'grid', gap: '0.75rem', gridTemplateColumns: '1fr 140px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Descrizione *</label>
            <input style={ricevuteInputStyle} value={form.descrizione} onChange={(e) => setForm({ ...form, descrizione: e.target.value })} placeholder="es. Marca da bollo €16,00" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Importo (€)</label>
            <input type="number" min="0" step="0.01" style={ricevuteInputStyle} value={form.importo} onChange={(e) => setForm({ ...form, importo: e.target.value })} placeholder="0,00" />
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
          Aggiungi
        </button>
      </div>

      <div style={ricevuteCardStyle}>
        <h2 style={{ margin: '0 0 1rem', fontSize: '1rem' }}>Elenco ({rows.length})</h2>
        {loading ? (
          <p style={{ color: 'var(--text-muted)' }}>Caricamento...</p>
        ) : rows.length === 0 ? (
          <p style={{ color: 'var(--text-muted)' }}>Nessun valore bollato registrato.</p>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="closures-table">
              <thead>
                <tr>
                  <th>Descrizione</th>
                  <th style={{ textAlign: 'right' }}>Importo</th>
                  <th style={{ width: '120px' }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    {editingId === row.id ? (
                      <>
                        <td><input style={ricevuteInputStyle} value={editForm.descrizione} onChange={(e) => setEditForm({ ...editForm, descrizione: e.target.value })} /></td>
                        <td><input type="number" min="0" step="0.01" style={{ ...ricevuteInputStyle, textAlign: 'right' }} value={editForm.importo} onChange={(e) => setEditForm({ ...editForm, importo: e.target.value })} /></td>
                        <td>
                          <div style={{ display: 'flex', gap: '0.35rem' }}>
                            <button type="button" onClick={handleSaveEdit} disabled={saving} style={{ background: 'var(--accent)', border: 'none', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'white' }}><Save size={16} /></button>
                            <button type="button" onClick={() => setEditingId(null)} style={{ background: 'transparent', border: '1px solid var(--border)', borderRadius: '6px', padding: '0.35rem', cursor: 'pointer', color: 'var(--text-muted)' }}><X size={16} /></button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td style={{ fontWeight: 600 }}>{row.descrizione}</td>
                        <td style={{ textAlign: 'right' }}>€ {Number(row.importo).toFixed(2)}</td>
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
