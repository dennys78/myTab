import React, { useState, useEffect } from 'react';
import { Plus, Trash2, Loader2, Wallet, ArrowDownToLine } from 'lucide-react';
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
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

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
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImporto('');
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
    <div style={{ maxWidth: '750px', margin: '0 auto' }}>
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
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Importo Versato (€)</label>
              <input type="number" min="0.01" step="0.01" value={importo}
                onChange={e => setImporto(e.target.value)}
                placeholder="0.00"
                style={{ ...inp, width: '100%', boxSizing: 'border-box' }} />
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
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {['Data', 'Operatore', 'Saldo Prec.', 'Importo Versato', 'Saldo Dopo', ...(isAdmin ? [''] : [])].map(h => (
                    <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.8rem', color: 'var(--text-muted)', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {versamenti.map(v => {
                  const saldoDopo = v.saldo_precedente - v.importo_versato;
                  return (
                    <tr key={v.id} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.85rem 1rem', whiteSpace: 'nowrap' }}>
                        {new Date(v.date).toLocaleDateString('it-IT')}
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>{v.operator}</td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600 }}>
                        € {v.saldo_precedente.toFixed(2)}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: 'var(--accent)' }}>
                        − € {v.importo_versato.toFixed(2)}
                      </td>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 700, color: saldoDopo >= 0 ? '#22c55e' : 'var(--danger)' }}>
                        € {saldoDopo.toFixed(2)}
                      </td>
                      {isAdmin && (
                        <td style={{ padding: '0.85rem 1rem' }}>
                          <button onClick={() => handleDelete(v.id)}
                            style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}>
                            <Trash2 size={16} />
                          </button>
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
