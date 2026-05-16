import React, { useState, useEffect, useRef } from 'react';
import { Save, Loader2, X, Plus, Sparkles, Calculator, Camera, Images } from 'lucide-react';

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
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const filesRef = useRef([]);            // ref stabile per evitare stale closure su mobile
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [saving, setSaving] = useState(false);

  // Rigenera thumbnail ogni volta che cambia la lista file
  useEffect(() => {
    const urls = filesRef.current.map(f => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach(u => URL.revokeObjectURL(u));
  }, [files]);

  const addFiles = (e) => {
    if (!e.target.files?.length) return;
    const incoming = Array.from(e.target.files);
    // Usa ref per evitare qualsiasi problema di closure stale su iOS
    const next = [...filesRef.current, ...incoming].slice(0, 2);
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
    fetch('/api/closures/extract-ai/', { method: 'POST', body: fd })
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

  const handleItemChange = (id, field, value) => {
    setPreviewData(prev => ({
      ...prev,
      items: prev.items.map(item => {
        if (item.id !== id) return item;
        const upd = { ...item, [field]: field === 'descrizione' ? value : (parseFloat(value) || 0) };
        if (field === 'entrate' || field === 'uscite')
          upd.saldo = Math.round((upd.entrate - upd.uscite) * 100) / 100;
        return upd;
      }),
    }));
  };

  const calcDifferenza = (s) => {
    const atteso = (s.totale || 0) - (s.pag_pos || 0) - (s.distrib || 0) - (s.reso_auto || 0) - (s.reso_cont || 0);
    return Math.round(((s.totale_cassetto || 0) - atteso) * 100) / 100;
  };

  const handleSummaryChange = (e) => {
    const { name, value } = e.target;
    setPreviewData(prev => {
      const updated = { ...prev.summary, [name]: parseFloat(value) || 0 };
      updated.differenza = calcDifferenza(updated);
      return { ...prev, summary: updated };
    });
  };

  const addItem = () => setPreviewData(prev => ({
    ...prev,
    items: [...prev.items, { id: `n${Date.now()}`, descrizione: '', entrate: 0, uscite: 0, saldo: 0 }],
  }));

  const removeItem = (id) => setPreviewData(prev => ({ ...prev, items: prev.items.filter(i => i.id !== id) }));

  const handleAcquire = () => {
    setSaving(true);
    setError(null);
    fetch('/api/closures/insert/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: previewData.date,
        operator: 'IA Groq',
        summary: previewData.summary,
        items: previewData.items.map(({ id, ...r }) => r),
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success' || d.id) { alert('Acquisizione completata!'); onBack(); }
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

  // ─── PREVIEW ────────────────────────────────────────────────────────────────
  if (previewData) {
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
            {Object.keys(previewData.summary).map(key => {
              const val = previewData.summary[key];
              const label = key.replace(/_/g, ' ');
              if (key === 'differenza') {
                return (
                  <div key={key}>
                    <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'capitalize' }}>
                      {label}
                    </label>
                    <div style={{
                      padding: '0.5rem 0.6rem', borderRadius: '6px', fontWeight: 700, fontSize: '1rem',
                      border: '1px solid var(--border)', background: 'var(--bg-dark)',
                      color: val > 0 ? '#22c55e' : val < 0 ? 'var(--danger)' : 'var(--text-muted)',
                    }}>
                      {val >= 0 ? '+' : ''}{val.toFixed(2)}
                    </div>
                  </div>
                );
              }
              return (
                <div key={key}>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.3rem', textTransform: 'capitalize' }}>
                    {label}
                  </label>
                  <input type="number" name={key}
                    value={val === 0 ? '' : val}
                    onChange={handleSummaryChange} placeholder="0.00"
                    style={{ ...inp(), width: '100%' }} />
                </div>
              );
            })}
          </div>
        </div>

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
                      <input type="text" value={item.descrizione}
                        onChange={e => handleItemChange(item.id, 'descrizione', e.target.value)}
                        placeholder="Nome Reparto"
                        style={{ ...inp({ width: '100%', minWidth: isMobile ? '110px' : '150px' }) }} />
                    </td>
                    <td>
                      <input type="number" value={item.entrate === 0 ? '' : item.entrate}
                        onChange={e => handleItemChange(item.id, 'entrate', e.target.value)}
                        placeholder="0.00"
                        style={{ ...inp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <input type="number" value={item.uscite === 0 ? '' : item.uscite}
                        onChange={e => handleItemChange(item.id, 'uscite', e.target.value)}
                        placeholder="0.00"
                        style={{ ...inp({ width: isMobile ? '75px' : '95px' }) }} />
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-block', minWidth: isMobile ? '60px' : '80px',
                        padding: '0.5rem 0.4rem', fontWeight: '600', fontSize: '0.9rem',
                        color: item.saldo > 0 ? '#22c55e' : item.saldo < 0 ? 'var(--danger)' : 'var(--text-muted)',
                      }}>
                        {item.saldo.toFixed(2)}
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
  const atLimit = files.length >= 2;

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto' }}>
      <h1 style={{ textAlign: 'center', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
        <Sparkles size={26} color="var(--accent)" /> Acquisisci con IA
      </h1>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', marginBottom: '0.4rem', fontSize: '0.9rem' }}>
        Carica fino a 2 immagini — Groq (Llama 4 Scout) analizza la chiusura e restituisce i dati strutturati.
      </p>
      <p style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.78rem', marginBottom: '2rem' }}>
        Gratuito · Alta precisione anche con foto sfocate o storte
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.9rem 1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          {error}
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
              Hai raggiunto il limite di 2 foto. Premi <strong style={{ color: 'white' }}>Analizza</strong> per procedere oppure rimuovi una foto per aggiungerne un'altra.
            </p>
          )}
        </div>
      ) : (
        /* ── DESKTOP: area dashed classica ── */
        <div style={{ border: '2px dashed var(--border)', borderRadius: '12px', padding: '3rem 2rem', background: 'rgba(255,255,255,0.02)', marginBottom: '1.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
          <Sparkles size={48} color="var(--accent)" />
          <h3 style={{ margin: 0 }}>Seleziona Immagini</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>PNG, JPG o JPEG — Max 2 file</p>
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
            {atLimit ? 'Limite 2 file raggiunto' : 'Sfoglia File'}
          </label>
        </div>
      )}

      {/* Anteprima foto accumulate */}
      {files.length > 0 && (
        <div style={{ marginBottom: '1.5rem' }}>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.75rem' }}>
            {files.length}/2 {files.length === 1 ? 'foto selezionata' : 'foto selezionate'}
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
        {loading ? <><Loader2 size={22} className="spin" /> Analisi IA in corso...</> : <><Sparkles size={20} /> Analizza con Groq IA</>}
      </button>
    </div>
  );
}
