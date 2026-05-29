import { useState, useEffect, useRef } from 'react';
import { Save, Loader2, X, Plus, Sparkles, Calculator, Camera, Images, Trash2 } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import { MAX_ACQUISITION_FILES } from './acquisitionConfig';

function useIsMobile() {
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 768px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 768px)');
    const h = (e) => setMobile(e.matches);
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, []);
  return mobile;
}

export default function AcquisisciChiusureAI({ onBack }) {
  const isMobile = useIsMobile();
  const { user } = useAuth();
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const filesRef = useRef([]);            // ref stabile per evitare stale closure su mobile
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [loadingDraftId, setLoadingDraftId] = useState(null);
  const [deletingDraftId, setDeletingDraftId] = useState(null);
  const [aiProvider, setAiProvider] = useState('groq');

  const fetchDrafts = () => {
    apiFetch('/api/acquisition-drafts/')
      .then(r => r.json())
      .then(d => { if (d.status === 'success') setDrafts(d.data); })
      .catch(() => {});
  };

  useEffect(() => { fetchDrafts(); }, []);

  useEffect(() => {
    apiFetch('/api/acquisition/ai-provider/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setAiProvider(d.data.provider || 'groq');
        }
      })
      .catch(() => {});
  }, [user?.active_company_id]);

  const analyzeButtonLabel = aiProvider === 'gemini' ? 'Analizza con Gemini IA' : 'Analizza con Groq IA';
  const providerLabel = aiProvider === 'gemini' ? 'Gemini' : 'Groq';

  // Rigenera thumbnail ogni volta che cambia la lista file
  useEffect(() => {
    const urls = filesRef.current.map(f => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach(u => URL.revokeObjectURL(u));
  }, [files]);

  const addFiles = (e) => {
    if (!e.target.files?.length) return;
    const remaining = MAX_ACQUISITION_FILES - filesRef.current.length;
    if (remaining <= 0) return;
    const incoming = Array.from(e.target.files).slice(0, remaining);
    // Usa ref per evitare qualsiasi problema di closure stale su iOS
    const next = [...filesRef.current, ...incoming].slice(0, MAX_ACQUISITION_FILES);
    filesRef.current = next;
    setFiles([...next]);
    e.target.value = '';          // permette di ri-selezionare lo stesso file
  };

  const removeFile = (index) => {
    const next = filesRef.current.filter((_, i) => i !== index);
    filesRef.current = next;
    setFiles([...next]);
  };

  const handleExtract = () => {
    if (!filesRef.current.length) return;
    setLoading(true);
    setError(null);
    const fd = new FormData();
    filesRef.current.forEach((f, i) => fd.append(`file${i}`, f));
    apiFetch('/api/closures/extract-ai/', { method: 'POST', body: fd })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          const enriched = {
            ...d.data,
            items: d.data.items.map((item, i) => ({ ...item, id: `t${i}` })),
          };
          if (!enriched.date) enriched.date = new Date().toISOString().split('T')[0];
          setPreviewData(enriched);
        } else {
          setError(d.error || 'Errore durante l\'estrazione.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoading(false));
  };

  const loadDraft = (draftId) => {
    setLoadingDraftId(draftId);
    setError(null);
    apiFetch(`/api/acquisition-drafts/${draftId}/extract-ai/`, { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          const enriched = {
            ...d.data,
            items: d.data.items.map((item, i) => ({ ...item, id: `d${draftId}_${i}` })),
          };
          if (!enriched.date) enriched.date = new Date().toISOString().split('T')[0];
          setPreviewData(enriched);
        } else {
          setError(d.error || 'Errore durante il caricamento della bozza.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setLoadingDraftId(null));
  };

  const removeDraft = (draft) => {
    if (!window.confirm(`Rimuovere la bozza di ${draft.operator || 'Telegram'}? L'incasso non verrà registrato.`)) return;
    setDeletingDraftId(draft.id);
    setError(null);
    apiFetch(`/api/acquisition-drafts/${draft.id}/cancel/`, { method: 'POST' })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setDrafts(prev => prev.filter(item => item.id !== draft.id));
        } else {
          setError(d.error || 'Errore durante la rimozione della bozza.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setDeletingDraftId(null));
  };

  const calcItemSaldo = (item) => Math.round(((Number(item.entrate) || 0) - Math.abs(Number(item.uscite) || 0)) * 100) / 100;

  const handleItemChange = (id, field, value) => {
    setPreviewData(prev => {
      const items = prev.items.map(item => {
        if (item.id !== id) return item;
        const upd = { ...item, [field]: field === 'descrizione' ? value.toUpperCase() : (parseFloat(value) || 0) };
        if (field === 'uscite') upd.uscite = Math.abs(upd.uscite);
        if (field === 'entrate' || field === 'uscite') upd.saldo = calcItemSaldo(upd);
        return upd;
      });
      return {
        ...prev,
        items,
        summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) },
      };
    });
  };

  const calcSaldoReparti = (items) =>
    Math.round((items || []).reduce((sum, item) => sum + calcItemSaldo(item), 0) * 100) / 100;

  // Con i report giochi (5 foto): Differenza = Totale riportato da cassa - Somma algebrica saldi reparti
  const calcDifferenzaReparti = (s, items) =>
    Math.round(((s.totale || 0) - calcSaldoReparti(items)) * 100) / 100;

  // Solo foglio incasso (2 foto): vecchio calcolo basato sul totale scassettato
  const calcDifferenzaCassetto = (s) => {
    const atteso = (s.totale || 0) - (s.pag_pos || 0) - (s.distrib || 0) - (s.reso_auto || 0) - (s.reso_cont || 0);
    return Math.round(((s.totale_cassetto || 0) - atteso) * 100) / 100;
  };

  const calcDifferenza = (s, items, withReports) =>
    withReports ? calcDifferenzaReparti(s, items) : calcDifferenzaCassetto(s);

  const handleSummaryChange = (e) => {
    const { name, value } = e.target;
    setPreviewData(prev => {
      const updated = { ...prev.summary, [name]: parseFloat(value) || 0 };
      updated.differenza = calcDifferenza(updated, prev.items, prev.with_reports);
      return { ...prev, summary: updated };
    });
  };

  const addItem = () => setPreviewData(prev => {
    const items = [...prev.items, { id: `n${Date.now()}`, descrizione: '', entrate: 0, uscite: 0, saldo: 0 }];
    return { ...prev, items, summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) } };
  });

  const removeItem = (id) => setPreviewData(prev => {
    const items = prev.items.filter(i => i.id !== id);
    return { ...prev, items, summary: { ...prev.summary, differenza: calcDifferenza(prev.summary, items, prev.with_reports) } };
  });

  const handleAcquire = () => {
    const cleanItems = previewData.items.map(item => {
      const cleanItem = { ...item, uscite: Math.abs(Number(item.uscite) || 0), saldo: calcItemSaldo(item) };
      delete cleanItem.id;
      return cleanItem;
    });
    const withReports = !!previewData.with_reports;
    const summaryPayload = {
      ...previewData.summary,
      totale_cassetto: withReports ? 0 : (previewData.summary.totale_cassetto || 0),
      differenza: calcDifferenza(previewData.summary, previewData.items, withReports),
    };
    setSaving(true);
    setError(null);
    apiFetch('/api/closures/insert/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: previewData.date,
        operator: user?.username || 'IA Groq',
        summary: summaryPayload,
        items: cleanItems,
        draft_id: previewData.draft_id,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success' || d.id) { alert('Chiusura cassa registrata correttamente in myTab.'); fetchDrafts(); onBack(); }
        else setError(d.error || 'Errore salvataggio.');
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const inp = (extra = {}) => ({
    padding: '0.5rem 0.6rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.9rem',
    ...extra,
  });

  const summaryLabel = (key) => ({
    totale: 'Totale riportato da cassa',
    totale_cassetto: 'Totale scassettato',
    differenza: 'Differenza',
  }[key] || key.replace(/_/g, ' '));

  // ─── PREVIEW ────────────────────────────────────────────────────────────────
  if (previewData) {
    const regularSummaryEntries = Object.entries(previewData.summary).filter(
      ([key]) => !['totale_cassetto', 'differenza'].includes(key)
    );
    const withReports = !!previewData.with_reports;
    const saldoTotaleReparti = previewData.items.reduce((sum, item) => sum + calcItemSaldo(item), 0);
    const totaleScassettato = previewData.summary.totale_cassetto ?? 0;
    const differenza = calcDifferenza(previewData.summary, previewData.items, withReports);
    const previewImages = previewData.images?.length
      ? previewData.images
      : previews.map((url, index) => ({ id: `local_${index}`, url }));

    return (
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '0.75rem' }}>
          <h1 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: isMobile ? '1.2rem' : '1.75rem' }}>
            <Sparkles size={isMobile ? 20 : 24} color="var(--accent)" />
            Anteprima Estrazione IA
          </h1>
          <button onClick={() => setPreviewData(null)}
            style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-main)', borderRadius: '6px', cursor: 'pointer', whiteSpace: 'nowrap' }}>
            ← Ricarica
          </button>
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.75rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
            {error}
          </div>
        )}

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
            <Calculator size={18} color="var(--accent)" /> Dati Generali
          </h2>
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>Data Chiusura</label>
            <input type="date" value={previewData.date}
              onChange={e => setPreviewData(p => ({ ...p, date: e.target.value }))}
              style={{ ...inp(), width: isMobile ? '100%' : '200px' }} />
          </div>
          <div className="acq-summary-grid">
            {regularSummaryEntries.map(([key, val]) => {
              return (
                <div key={key}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'capitalize' }}>
                    {summaryLabel(key)}
                  </label>
                  <input type="number" name={key}
                    value={val === 0 ? '' : val}
                    onChange={handleSummaryChange} placeholder="0.00"
                    style={{ ...inp(), width: '100%' }} />
                </div>
              );
            })}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: isMobile ? '1fr' : '1fr 1fr',
            gap: '1rem',
            padding: '1rem',
            border: '1px solid var(--border-strong)',
            borderRadius: '14px',
            background: 'rgba(79, 141, 247, 0.08)',
          }}>
            {withReports ? (
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Somma algebrica saldi reparti
                </label>
                <div style={{
                  padding: '0.62rem 0.75rem',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '1.1rem',
                  border: '1px solid var(--border-strong)',
                  background: 'var(--bg-dark)',
                  color: 'var(--text-main)',
                }}>
                  {saldoTotaleReparti.toFixed(2)}
                </div>
              </div>
            ) : (
              <div>
                <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                  Totale scassettato
                </label>
                <input
                  type="number"
                  name="totale_cassetto"
                  value={totaleScassettato === 0 ? '' : totaleScassettato}
                  onChange={handleSummaryChange}
                  placeholder="0.00"
                  style={{ ...inp({ width: '100%', fontSize: '1.1rem', fontWeight: 700, borderColor: 'var(--accent)' }) }}
                />
              </div>
            )}
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Differenza
              </label>
              <div style={{
                padding: '0.62rem 0.75rem',
                borderRadius: '10px',
                fontWeight: 800,
                fontSize: '1.1rem',
                border: '1px solid var(--border-strong)',
                background: 'var(--bg-dark)',
                color: differenza > 0 ? 'var(--success)' : differenza < 0 ? 'var(--danger)' : 'var(--text-muted)',
              }}>
                {differenza >= 0 ? '+' : ''}{Number(differenza).toFixed(2)}
              </div>
            </div>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', margin: '0.6rem 0 0' }}>
            {withReports
              ? 'Differenza = Totale riportato da cassa − Somma algebrica saldi reparti'
              : 'Differenza = Totale scassettato − (Totale − Pag.Pos − Distrib. − Resi)'}
          </p>
        </div>

        {previewImages.length > 0 && (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
            <h2 style={{ margin: '0 0 1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '1rem' }}>
              <Images size={18} color="var(--accent)" /> Foto importazione
            </h2>
            <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.9rem' }}>
              {previewImages.map((image, index) => (
                <a key={image.id} href={image.url} target="_blank" rel="noreferrer" style={{ display: 'block', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden', background: 'var(--bg-dark)', textDecoration: 'none' }}>
                  <img
                    src={image.url}
                    alt={`Foto importazione ${index + 1}`}
                    style={{ width: '100%', height: isMobile ? '180px' : '150px', objectFit: 'cover', display: 'block' }}
                  />
                  <div style={{ padding: '0.55rem 0.7rem', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                    Foto {index + 1}
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: isMobile ? '1rem' : '1.5rem', marginBottom: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>Voci di Reparto</h2>
            <button onClick={addItem}
              style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.4rem 0.8rem', background: 'rgba(59,130,246,0.1)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
              <Plus size={15} /> Aggiungi
            </button>
          </div>

          <div className="table-responsive-wrapper">
            <table className="acq-items-table">
              <thead>
                <tr>
                  <th>Descrizione</th>
                  <th>Entrate</th>
                  <th>Uscite</th>
                  <th>Saldo</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {previewData.items.length === 0 && (
                  <tr><td colSpan="5" style={{ textAlign: 'center', padding: '1.5rem', color: 'var(--text-muted)' }}>Nessuna voce. Clicca Aggiungi.</td></tr>
                )}
                {previewData.items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <input className="acq-edit-input" type="text" value={item.descrizione}
                        onChange={e => handleItemChange(item.id, 'descrizione', e.target.value)}
                        placeholder="Nome Reparto"
                        style={{ ...inp({ width: '100%', minWidth: isMobile ? '110px' : '150px' }) }} />
                    </td>
                    <td>
                      <input className="acq-edit-input" type="number" value={item.entrate === 0 ? '' : item.entrate}
                        onChange={e => handleItemChange(item.id, 'entrate', e.target.value)}
                        placeholder="0.00"
                        style={{ ...inp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <input className="acq-edit-input" type="number" value={item.uscite === 0 ? '' : item.uscite}
                        onChange={e => handleItemChange(item.id, 'uscite', e.target.value)}
                        placeholder="0.00"
                        style={{ ...inp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-block', minWidth: isMobile ? '60px' : '80px',
                        padding: '0.5rem 0.4rem', fontWeight: '600', fontSize: '0.9rem',
                        color: calcItemSaldo(item) > 0 ? '#22c55e' : calcItemSaldo(item) < 0 ? 'var(--danger)' : 'var(--text-muted)',
                      }}>
                        {calcItemSaldo(item).toFixed(2)}
                      </span>
                    </td>
                    <td>
                      <button onClick={() => removeItem(item.id)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.4rem' }}>
                        <X size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {previewData.items.length > 0 && (
                  <tr className="acq-total-row">
                    <td colSpan="3">Somma algebrica saldi reparti</td>
                    <td>
                      <span className={saldoTotaleReparti > 0 ? 'success' : saldoTotaleReparti < 0 ? 'danger' : ''}>
                        {saldoTotaleReparti.toFixed(2)}
                      </span>
                    </td>
                    <td></td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="acq-actions">
          <button onClick={onBack}
            style={{ padding: '0.85rem 1.5rem', background: 'transparent', border: '1px solid var(--border)', color: 'white', borderRadius: '8px', cursor: 'pointer' }}>
            Annulla
          </button>
          <button onClick={handleAcquire} disabled={saving}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '0.85rem 1.5rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}>
            {saving ? <Loader2 size={20} className="spin" /> : <Save size={20} />}
            {saving ? 'Acquisizione...' : 'Acquisisci e Salva'}
          </button>
        </div>
      </div>
    );
  }

  // ─── UPLOAD ─────────────────────────────────────────────────────────────────
  const atLimit = files.length >= MAX_ACQUISITION_FILES;

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <Sparkles size={26} color="var(--accent)" /> Acquisisci con IA
      </h1>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', marginBottom: '0.4rem', fontSize: '0.9rem' }}>
        Carica fino a {MAX_ACQUISITION_FILES} immagini nell&apos;ordine indicato sotto.
      </p>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.78rem', marginBottom: '0.4rem', lineHeight: 1.45 }}>
        Includi il riepilogo chiusura cassa (tutti i reparti) più i report Lottomatica, Gratta e Vinci, Sisal.
        L&apos;ordine delle foto viene riconosciuto automaticamente.
      </p>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.78rem', marginBottom: '1.5rem' }}>
        Modello attivo: <strong style={{ color: 'var(--text-main)' }}>{providerLabel}</strong>
        {' '}— modificalo in <strong style={{ color: 'var(--text-main)' }}>Impostazioni</strong>
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.9rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          {error}
        </div>
      )}

      {drafts.length > 0 && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '14px', padding: '1rem', marginBottom: '1.5rem' }}>
          <h2 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>Bozze ricevute da Telegram</h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {drafts.map(draft => (
              <div key={draft.id} style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1fr auto', alignItems: 'center', gap: '0.75rem', padding: '0.75rem', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '10px' }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, marginBottom: '0.15rem' }}>
                    {draft.operator || 'Telegram'} · {draft.photo_count} foto
                  </div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                    Totale scassettato € {Number(draft.totale_scassettato).toFixed(2)} · {new Date(draft.created_at).toLocaleString('it-IT')}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'nowrap', justifyContent: isMobile ? 'flex-start' : 'flex-end', whiteSpace: 'nowrap' }}>
                  <button
                    onClick={() => loadDraft(draft.id)}
                    disabled={loadingDraftId === draft.id || deletingDraftId === draft.id}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 0.9rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
                  >
                    {loadingDraftId === draft.id ? <Loader2 size={16} className="spin" /> : <Sparkles size={16} />}
                    Carica bozza
                  </button>
                  <button
                    onClick={() => removeDraft(draft)}
                    disabled={loadingDraftId === draft.id || deletingDraftId === draft.id}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.55rem 0.8rem', background: 'transparent', color: 'var(--danger)', border: '1px solid var(--danger)', borderRadius: '8px', cursor: 'pointer', fontWeight: 700 }}
                  >
                    {deletingDraftId === draft.id ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}
                    Rimuovi
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Upload area */}
      {isMobile ? (
        /* ── MOBILE: pulsanti grandi ── */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '1.5rem' }}>
          {/* Fotocamera (rear camera) */}
          <input type="file" id="ai-camera" accept="image/*" capture="environment" onChange={addFiles} style={{ display: 'none' }} />
          <label htmlFor="ai-camera" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem',
            padding: '1.25rem',
            background: atLimit ? 'var(--bg-card)' : 'var(--accent)',
            color: atLimit ? 'var(--text-muted)' : 'white',
            border: atLimit ? '1px solid var(--border)' : 'none',
            borderRadius: '12px',
            cursor: atLimit ? 'not-allowed' : 'pointer',
            fontSize: '1.1rem', fontWeight: '600',
            pointerEvents: atLimit ? 'none' : 'auto',
          }}>
            <Camera size={26} /> Scatta Foto
          </label>

          {/* Galleria */}
          <input type="file" id="ai-gallery" accept="image/*" multiple onChange={addFiles} style={{ display: 'none' }} />
          <label htmlFor="ai-gallery" style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.75rem',
            padding: '1.25rem',
            background: 'var(--bg-card)',
            color: atLimit ? 'var(--text-muted)' : 'var(--text-main)',
            border: `1px solid ${atLimit ? 'var(--border)' : 'var(--accent)'}`,
            borderRadius: '12px',
            cursor: atLimit ? 'not-allowed' : 'pointer',
            fontSize: '1.1rem', fontWeight: '600',
            pointerEvents: atLimit ? 'none' : 'auto',
          }}>
            <Images size={26} /> Dalla Galleria
          </label>

          {atLimit && (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem', margin: 0 }}>
              Hai raggiunto il limite di {MAX_ACQUISITION_FILES} foto. Premi <strong style={{ color: 'white' }}>Analizza</strong> per procedere oppure rimuovi una foto per aggiungerne un&apos;altra.
            </p>
          )}
        </div>
      ) : (
        /* ── DESKTOP: area dashed classica ── */
        <div style={{ border: '2px dashed var(--border)', borderRadius: '12px', padding: '3rem 2rem', background: 'rgba(255,255,255,0.02)', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <Sparkles size={48} color="var(--accent)" />
          <h3 style={{ margin: 0 }}>Seleziona Immagini</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>PNG, JPG o JPEG — Max {MAX_ACQUISITION_FILES} file</p>
          <input type="file" id="ai-file-desktop" multiple accept="image/*" onChange={addFiles} style={{ display: 'none' }} />
          <label htmlFor="ai-file-desktop" style={{
            padding: '0.75rem 1.5rem',
            background: atLimit ? 'var(--bg-dark)' : 'var(--bg-card)',
            border: '1px solid var(--border)',
            color: atLimit ? 'var(--text-muted)' : 'white',
            borderRadius: '8px',
            cursor: atLimit ? 'not-allowed' : 'pointer',
            marginTop: '0.5rem',
            pointerEvents: atLimit ? 'none' : 'auto',
          }}>
            {atLimit ? `Limite ${MAX_ACQUISITION_FILES} file raggiunto` : 'Sfoglia File'}
          </label>
        </div>
      )}

      {/* Anteprima foto accumulate */}
      {files.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            {files.length}/{MAX_ACQUISITION_FILES} {files.length === 1 ? 'foto selezionata' : 'foto selezionate'}
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {files.map((file, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', background: 'var(--bg-card)', padding: '0.6rem 0.75rem', borderRadius: '10px', border: '1px solid var(--border)' }}>
                {/* Thumbnail */}
                {previews[i] && (
                  <img
                    src={previews[i]}
                    alt={`Foto ${i + 1}`}
                    style={{ width: '56px', height: '56px', objectFit: 'cover', borderRadius: '6px', flexShrink: 0 }}
                  />
                )}
                <div style={{ flex: 1, overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-main)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Foto {i + 1}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {file.name}
                  </div>
                </div>
                <button onClick={() => removeFile(i)} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', flexShrink: 0, padding: '0.25rem' }}>
                  <X size={18} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Pulsante analisi */}
      <button onClick={handleExtract} disabled={!files.length || loading}
        style={{
          width: '100%', padding: '1rem',
          background: files.length ? 'var(--accent)' : 'var(--bg-card)',
          color: files.length ? 'white' : 'var(--text-muted)',
          border: 'none', borderRadius: '10px', fontSize: '1rem', fontWeight: 'bold',
          cursor: files.length && !loading ? 'pointer' : 'not-allowed',
          display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem',
          minHeight: '54px',
        }}>
        {loading ? <><Loader2 size={22} className="spin" /> Analisi IA in corso...</> : <><Sparkles size={20} /> {analyzeButtonLabel}</>}
      </button>
    </div>
  );
}
