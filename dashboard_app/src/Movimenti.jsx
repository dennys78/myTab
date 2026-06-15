import { useState, useEffect, useMemo, Fragment } from 'react';
import { Plus, Trash2, Loader2, ArrowLeftRight, Pencil, Check, X, Bookmark, TrendingUp, TrendingDown } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import { getPeriodStart } from './dateFilters';
import StoricoPeriodHeader from './StoricoPeriodHeader';

const TIPO_ENTRATA = 'ENTRATA';
const TIPO_USCITA = 'USCITA';

export default function Movimenti({ initialEditId = null, onEditConsumed, onDataChange }) {
  const { user } = useAuth();
  const isAdmin = user?.role === 'amministratore';

  const [estrattoRighe, setEstrattoRighe] = useState([]);
  const [rettificaSaldo, setRettificaSaldo] = useState(0);
  const [saldoCassa, setSaldoCassa] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [tipo, setTipo] = useState(TIPO_ENTRATA);
  const [importo, setImporto] = useState('');
  const [note, setNote] = useState('');
  const [ricordaPromemoria, setRicordaPromemoria] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [editingId, setEditingId] = useState(null);
  const [editRow, setEditRow] = useState({});
  const [updating, setUpdating] = useState(false);
  const [storicoFiltro, setStoricoFiltro] = useState('week');

  const estrattoPeriodo = useMemo(() => {
    const start = getPeriodStart(storicoFiltro);
    const all = estrattoRighe;
    const before = all.filter((r) => new Date(`${r.date}T12:00:00`) < start);
    const inPeriod = all.filter((r) => new Date(`${r.date}T12:00:00`) >= start);
    const saldoIniziale = inPeriod.length > 0
      ? inPeriod[0].saldo_precedente
      : (before.length > 0 ? before[before.length - 1].saldo : rettificaSaldo);
    const saldoFinale = inPeriod.length > 0
      ? inPeriod[inPeriod.length - 1].saldo
      : saldoIniziale;
    return { saldoIniziale, righe: inPeriod, saldoFinale };
  }, [estrattoRighe, storicoFiltro, rettificaSaldo]);

  const startEdit = (row) => {
    setEditingId(row.ref_id);
    setEditRow({
      date: row.date,
      tipo: row.tipo,
      importo: row.entrata ?? row.uscita,
      note: row.note || '',
      ricorda_promemoria: !!row.ricorda_promemoria,
    });
  };
  const cancelEdit = () => { setEditingId(null); setEditRow({}); };

  const saveEdit = () => {
    setUpdating(true);
    apiFetch(`/api/movimenti-cassa/${editingId}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: editRow.date,
        tipo: editRow.tipo,
        importo: parseFloat(editRow.importo) || 0,
        note: editRow.note || '',
        ricorda_promemoria: !!editRow.ricorda_promemoria,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          cancelEdit();
          fetchData();
          onDataChange?.();
        }
      })
      .catch(() => {})
      .finally(() => setUpdating(false));
  };

  const fetchData = () => {
    setLoading(true);
    apiFetch('/api/cassa-estratto-conto/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setEstrattoRighe(d.righe || []);
          setRettificaSaldo(d.rettifica_saldo || 0);
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
    if (!initialEditId || loading || estrattoRighe.length === 0) return;
    const target = estrattoRighe.find(r => r.kind === 'movimento' && r.ref_id === initialEditId);
    if (!target) return;
    startEdit(target);
    onEditConsumed?.();
    const t = window.setTimeout(() => {
      document.getElementById(`mov-row-${target.ref_id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 120);
    return () => window.clearTimeout(t);
  }, [initialEditId, loading, estrattoRighe]);

  const handleSave = (e) => {
    e.preventDefault();
    const imp = parseFloat(importo);
    if (!imp || imp <= 0) { setSaveError('Inserisci un importo valido'); return; }
    setSaving(true);
    setSaveError(null);
    apiFetch('/api/movimenti-cassa/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date,
        operator: user?.username || '',
        tipo,
        importo: imp,
        note,
        ricorda_promemoria: ricordaPromemoria,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImporto('');
          setNote('');
          setRicordaPromemoria(false);
          setTipo(TIPO_ENTRATA);
          setDate(new Date().toISOString().split('T')[0]);
          fetchData();
          onDataChange?.();
        } else {
          setSaveError(d.error || 'Errore salvataggio');
        }
      })
      .catch(() => setSaveError('Errore di rete'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!window.confirm('Eliminare questo movimento?')) return;
    apiFetch(`/api/movimenti-cassa/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          fetchData();
          onDataChange?.();
        }
      })
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

  const formatSaldo = (value) => {
    const n = Number(value);
    if (!Number.isFinite(n)) return '—';
    return `€ ${n.toFixed(2)}`;
  };

  const formatDataBreve = (dateStr) => {
    const d = new Date(`${dateStr}T12:00:00`);
    return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit' });
  };

  const formatColImporto = (value) => {
    if (value == null || value === '') return '—';
    return `€ ${Number(value).toFixed(2)}`;
  };

  const editInpStyle = (isEntrata) => ({
    padding: '0.35rem 0.45rem',
    background: 'var(--bg-dark)',
    border: `2px solid ${isEntrata ? 'rgba(34, 197, 94, 0.55)' : 'rgba(239, 68, 68, 0.55)'}`,
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.85rem',
  });

  const kindLabel = (kind) => {
    if (kind === 'chiusura') return 'Chiusura';
    if (kind === 'versamento') return 'Versamento';
    if (kind === 'rettifica') return 'Rettifica';
    return 'Movimento';
  };

  return (
    <div style={{ maxWidth: '1120px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Movimenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Registra entrate e uscite che modificano la disponibilità di cassa (oltre ai versamenti).
      </p>

      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px',
        padding: '1.25rem 1.5rem', marginBottom: '1.5rem',
        display: 'flex', alignItems: 'center', gap: '1rem',
      }}>
        <ArrowLeftRight size={28} color="var(--accent)" style={{ flexShrink: 0 }} />
        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
            Contanti in Cassa (disponibili)
          </div>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: saldoCassa >= 0 ? '#22c55e' : 'var(--danger)' }}>
            {saldoCassa === null ? '—' : `€ ${saldoCassa.toFixed(2)}`}
          </div>
        </div>
      </div>

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
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Note</label>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Descrizione del movimento..."
              rows={3}
              style={{ ...inp('entrata'), width: '100%', resize: 'vertical', fontFamily: 'inherit', lineHeight: 1.45, borderColor: 'var(--border)' }}
            />
          </div>

          <label className="vers-promemoria-flag">
            <input type="checkbox" checked={ricordaPromemoria} onChange={e => setRicordaPromemoria(e.target.checked)} />
            <Bookmark size={16} />
            <span>Ricorda come promemoria</span>
          </label>
          <p className="vers-promemoria-hint">
            Se attivo, compare nel riquadro promemoria movimenti in dashboard.
          </p>

          <button type="submit" disabled={saving || !importo} className="mov-submit-btn">
            {saving ? <Loader2 size={17} className="spin" /> : <Plus size={17} />}
            Registra Movimento
          </button>
        </form>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', overflow: 'hidden' }}>
        <StoricoPeriodHeader
          title="Estratto conto cassa"
          value={storicoFiltro}
          onChange={setStoricoFiltro}
        />
        <p className="mov-storico-hint">
          Chiusure cassa (scassettato), versamenti in banca e movimenti in ordine cronologico con saldo progressivo.
        </p>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : error ? (
          <div style={{ padding: '1.5rem', color: 'var(--danger)', fontSize: '0.9rem' }}>{error}</div>
        ) : estrattoRighe.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessuna operazione registrata.</div>
        ) : (
          <div className="table-responsive-wrapper">
            <table className="cassa-estratto-table">
              <thead>
                <tr>
                  <th>Data</th>
                  <th>Descrizione</th>
                  <th>Entrata (+)</th>
                  <th>Uscita (−)</th>
                  <th>Saldo intermedio</th>
                  {isAdmin && <th className="cassa-estratto-col-azioni">Azioni</th>}
                </tr>
              </thead>
              <tbody>
                <tr className="cassa-estratto-row cassa-estratto-row--summary">
                  <td>—</td>
                  <td>Saldo iniziale</td>
                  <td>—</td>
                  <td>—</td>
                  <td className="cassa-estratto-saldo">{formatSaldo(estrattoPeriodo.saldoIniziale)}</td>
                  {isAdmin && <td />}
                </tr>

                {estrattoPeriodo.righe.length === 0 ? (
                  <tr className="cassa-estratto-row cassa-estratto-row--empty">
                    <td colSpan={isAdmin ? 6 : 5}>Nessuna operazione nel periodo selezionato.</td>
                  </tr>
                ) : estrattoPeriodo.righe.map((r) => {
                  const isMovimento = r.kind === 'movimento';
                  const isEditing = isMovimento && editingId === r.ref_id;
                  const isEntrata = isEditing ? editRow.tipo === TIPO_ENTRATA : r.entrata != null;

                  return (
                    <Fragment key={`${r.kind}-${r.ref_id ?? 'rettifica'}-${r.date}-${r.saldo}`}>
                      <tr
                        id={isMovimento ? `mov-row-${r.ref_id}` : undefined}
                        className={`cassa-estratto-row cassa-estratto-row--${r.kind}${isEditing ? ' cassa-estratto-row--editing' : ''}`}
                      >
                        <td className="cassa-estratto-data">{formatDataBreve(r.date)}</td>
                        <td className="cassa-estratto-desc">
                          <span className={`cassa-estratto-kind cassa-estratto-kind--${r.kind}`}>{kindLabel(r.kind)}</span>
                          {r.descrizione}
                          {r.ricorda_promemoria && (
                            <span className="vers-promemoria-badge cassa-estratto-promemoria" title="Promemoria in dashboard">
                              <Bookmark size={11} /> Promemoria
                            </span>
                          )}
                        </td>
                        <td className="cassa-estratto-importo cassa-estratto-importo--entrata">
                          {formatColImporto(r.entrata)}
                        </td>
                        <td className="cassa-estratto-importo cassa-estratto-importo--uscita">
                          {formatColImporto(r.uscita)}
                        </td>
                        <td className="cassa-estratto-saldo">{formatSaldo(r.saldo)}</td>
                        {isAdmin && (
                          <td className="cassa-estratto-col-azioni">
                            {isMovimento && !isEditing && (
                              <div className="cassa-estratto-actions">
                                <button type="button" onClick={() => startEdit(r)} title="Modifica" className="cassa-estratto-action-btn cassa-estratto-action-btn--edit">
                                  <Pencil size={14} />
                                </button>
                                <button type="button" onClick={() => handleDelete(r.ref_id)} title="Elimina" className="cassa-estratto-action-btn cassa-estratto-action-btn--delete">
                                  <Trash2 size={14} />
                                </button>
                              </div>
                            )}
                          </td>
                        )}
                      </tr>

                      {isEditing && (
                        <tr className="cassa-estratto-row cassa-estratto-row--edit-form">
                          <td colSpan={isAdmin ? 6 : 5}>
                            <div className="cassa-estratto-edit-panel">
                              <div className="cassa-estratto-edit-grid">
                                <label>
                                  Data
                                  <input type="date" value={editRow.date} onChange={e => setEditRow(prev => ({ ...prev, date: e.target.value }))} style={editInpStyle(isEntrata)} />
                                </label>
                                <label>
                                  Tipo
                                  <select value={editRow.tipo} onChange={e => setEditRow(prev => ({ ...prev, tipo: e.target.value }))} style={editInpStyle(isEntrata)}>
                                    <option value={TIPO_ENTRATA}>Entrata</option>
                                    <option value={TIPO_USCITA}>Uscita</option>
                                  </select>
                                </label>
                                <label>
                                  Importo (€)
                                  <input type="number" min="0.01" step="0.01" value={editRow.importo} onChange={e => setEditRow(prev => ({ ...prev, importo: e.target.value }))} style={editInpStyle(isEntrata)} />
                                </label>
                              </div>
                              <label className="cassa-estratto-edit-note">
                                Note
                                <textarea value={editRow.note} onChange={e => setEditRow(prev => ({ ...prev, note: e.target.value }))} rows={2} style={{ ...editInpStyle(isEntrata), width: '100%', resize: 'vertical', fontFamily: 'inherit' }} />
                              </label>
                              <label className="vers-promemoria-flag vers-promemoria-flag--compact">
                                <input type="checkbox" checked={!!editRow.ricorda_promemoria} onChange={e => setEditRow(prev => ({ ...prev, ricorda_promemoria: e.target.checked }))} />
                                <Bookmark size={14} />
                                <span>Promemoria</span>
                              </label>
                              <div className="cassa-estratto-edit-actions">
                                <button type="button" onClick={saveEdit} disabled={updating} className="cassa-estratto-action-btn cassa-estratto-action-btn--save">
                                  {updating ? <Loader2 size={15} className="spin" /> : <Check size={15} />}
                                  Salva
                                </button>
                                <button type="button" onClick={cancelEdit} className="cassa-estratto-action-btn">
                                  <X size={15} /> Annulla
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}

                <tr className="cassa-estratto-row cassa-estratto-row--summary">
                  <td>—</td>
                  <td>Saldo finale</td>
                  <td>—</td>
                  <td>—</td>
                  <td className="cassa-estratto-saldo">{formatSaldo(estrattoPeriodo.saldoFinale)}</td>
                  {isAdmin && <td />}
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
