import { useState } from 'react';
import { Upload, FileImage, Calculator, Save, AlertCircle, Loader2, X, Plus } from 'lucide-react';
import { apiFetch } from './api';

export default function AcquisisciChiusure({ onBack }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [rawText, setRawText] = useState(null);
  const [showRaw, setShowRaw] = useState(false);

  const handleFileChange = (e) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).slice(0, 2);
      setFiles(selectedFiles);
    }
  };

  const handleRemoveFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleExtract = () => {
    if (files.length === 0) return;
    setLoading(true);
    setError(null);

    const formData = new FormData();
    files.forEach((file, index) => {
      formData.append(`file${index}`, file);
    });

    apiFetch('/api/closures/extract/', {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          // Initialize IDs for items to edit them easily
          const dataWithIds = {
            ...data.data,
            summary: {
              ...data.data.summary,
              totale_cassetto: data.data.summary?.totale_cassetto || 0,
              differenza: data.data.summary?.differenza || 0,
            },
            items: data.data.items.map((item, i) => ({ ...item, id: `temp_${i}` }))
          };
          if (!dataWithIds.date) {
            dataWithIds.date = new Date().toISOString().split('T')[0];
          }
          setPreviewData(dataWithIds);
          setRawText(data.data.raw_text || null);
        } else {
          setError(data.error || "Errore sconosciuto durante l'estrazione.");
        }
      })
      .catch(err => {
        console.error(err);
        setError("Errore di rete durante la comunicazione con il server.");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setPreviewData(prev => {
      const summary = {
        ...prev.summary,
        [name]: parseFloat(value) || 0
      };
      const atteso = (summary.totale || 0) - (summary.pag_pos || 0) - (summary.distrib || 0) - (summary.reso_auto || 0) - (summary.reso_cont || 0);
      summary.differenza = Math.round(((summary.totale_cassetto || 0) - atteso) * 100) / 100;
      return { ...prev, summary };
    });
  };

  const handleDateChange = (e) => {
    setPreviewData(prev => ({
      ...prev,
      date: e.target.value
    }));
  };

  const handleItemChange = (id, field, value) => {
    setPreviewData(prev => ({
      ...prev,
      items: prev.items.map(item => {
        if (item.id !== id) return item;
        const updated = {
          ...item,
          [field]: field === 'descrizione' ? value : (parseFloat(value) || 0),
        };
        if (field === 'entrate' || field === 'uscite') {
          updated.saldo = Math.round((updated.entrate - updated.uscite) * 100) / 100;
        }
        return updated;
      })
    }));
  };

  const handleAddItem = () => {
    setPreviewData(prev => ({
      ...prev,
      items: [
        ...prev.items,
        { id: `temp_new_${Date.now()}`, descrizione: '', entrate: 0, uscite: 0, saldo: 0 }
      ]
    }));
  };

  const handleRemoveItem = (id) => {
    setPreviewData(prev => ({
      ...prev,
      items: prev.items.filter(item => item.id !== id)
    }));
  };

  const handleManualEntry = () => {
    setPreviewData({
      date: new Date().toISOString().split('T')[0],
      summary: {
        contanti: 0,
        pag_pos: 0,
        cassa_auto: 0,
        reso_cont: 0,
        reso_auto: 0,
        distrib: 0,
        totale: 0,
        totale_cassetto: 0,
        differenza: 0,
      },
      items: []
    });
  };

  const summaryLabel = (key) => ({
    totale: 'Totale riportato da cassa',
    totale_cassetto: 'Totale scassettato',
    differenza: 'Differenza',
  }[key] || key.replace(/_/g, ' '));

  const handleAcquire = () => {
    setSaving(true);
    setError(null);
    
    // Remove temporary IDs
    const cleanItems = previewData.items.map(item => {
      const cleanItem = { ...item };
      delete cleanItem.id;
      return cleanItem;
    });
    const payload = {
      date: previewData.date,
      operator: 'Web Dashboard',
      summary: previewData.summary,
      items: cleanItems
    };

    apiFetch('/api/closures/insert/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' || data.id) {
          alert("Chiusura cassa registrata correttamente in myTab.");
          onBack(); // Go back to dashboard
        } else {
          setError(data.error || "Errore durante il salvataggio.");
        }
      })
      .catch(err => {
        console.error(err);
        setError("Errore di rete durante il salvataggio.");
      })
      .finally(() => {
        setSaving(false);
      });
  };

  if (previewData) {
    const regularSummaryEntries = Object.entries(previewData.summary).filter(
      ([key]) => !['totale_cassetto', 'differenza'].includes(key)
    );
    const totaleScassettato = previewData.summary.totale_cassetto ?? 0;
    const differenza = previewData.summary.differenza ?? 0;
    const saldoTotaleReparti = previewData.items.reduce((sum, item) => sum + (Number(item.saldo) || 0), 0);

    return (
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
          <h1>Anteprima Estrazione</h1>
          <button 
            onClick={() => setPreviewData(null)} 
            style={{ padding: '0.5rem 1rem', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-main)', borderRadius: '6px', cursor: 'pointer' }}
          >
            Ricarica Immagini
          </button>
        </div>

        {error && (
          <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)', padding: '1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <AlertCircle size={20} />
            {error}
          </div>
        )}

        {rawText && (
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1rem', marginBottom: '2rem' }}>
            <button
              onClick={() => setShowRaw(v => !v)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.85rem', padding: 0 }}
            >
              {showRaw ? '▲' : '▶'} Testo grezzo OCR (debug)
            </button>
            {showRaw && (
              <pre style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: '300px', overflowY: 'auto' }}>
                {rawText}
              </pre>
            )}
          </div>
        )}

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' }}>
          <h2 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Calculator size={20} color="var(--accent)" />
            Dati Generali
          </h2>
          
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Data Chiusura</label>
            <input 
              type="date" 
              value={previewData.date} 
              onChange={handleDateChange}
              style={{ padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px', width: '200px' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            {regularSummaryEntries.map(([key, val]) => (
              <div key={key}>
                <label style={{ display: 'block', fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'capitalize' }}>
                  {summaryLabel(key)}
                </label>
                <input 
                  type="number" 
                  name={key}
                  value={val === 0 ? '' : val} 
                  onChange={handleInputChange}
                  placeholder="0.00"
                  style={{ width: '100%', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                />
              </div>
            ))}
          </div>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '1rem',
            padding: '1rem',
            border: '1px solid var(--border-strong)',
            borderRadius: '14px',
            background: 'rgba(79, 141, 247, 0.08)',
          }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.35rem', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Totale scassettato
              </label>
              <input
                type="number"
                name="totale_cassetto"
                value={totaleScassettato === 0 ? '' : totaleScassettato}
                onChange={handleInputChange}
                placeholder="0.00"
                style={{ width: '100%', padding: '0.62rem 0.75rem', background: 'var(--bg-dark)', border: '1px solid var(--accent)', color: 'white', borderRadius: '10px', fontSize: '1.1rem', fontWeight: 700 }}
              />
            </div>
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
        </div>

        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0 }}>Voci di Reparto</h2>
            <button 
              onClick={handleAddItem}
              style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.5rem 1rem', background: 'rgba(59, 130, 246, 0.1)', color: 'var(--accent)', border: '1px solid var(--accent)', borderRadius: '6px', cursor: 'pointer' }}
            >
              <Plus size={16} /> Aggiungi Riga
            </button>
          </div>
          
          <div className="table-responsive-wrapper">
            <table>
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
                {previewData.items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <input
                        className="acq-edit-input"
                        type="text" 
                        value={item.descrizione} 
                        onChange={(e) => handleItemChange(item.id, 'descrizione', e.target.value)}
                        placeholder="Nome Reparto"
                        style={{ width: '100%', minWidth: '150px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <input
                        className="acq-edit-input"
                        type="number" 
                        value={item.entrate === 0 ? '' : item.entrate} 
                        onChange={(e) => handleItemChange(item.id, 'entrate', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <input
                        className="acq-edit-input"
                        type="number" 
                        value={item.uscite === 0 ? '' : item.uscite} 
                        onChange={(e) => handleItemChange(item.id, 'uscite', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <span style={{
                        display: 'inline-block',
                        width: '100px',
                        padding: '0.5rem',
                        fontWeight: '600',
                        color: item.saldo > 0 ? 'var(--success, #22c55e)' : item.saldo < 0 ? 'var(--danger)' : 'var(--text-muted)',
                      }}>
                        {item.saldo.toFixed(2)}
                      </span>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button 
                        onClick={() => handleRemoveItem(item.id)}
                        style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.5rem' }}
                        title="Rimuovi"
                      >
                        <X size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
                {previewData.items.length === 0 && (
                  <tr>
                    <td colSpan="5" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                      Nessun reparto estratto o inserito. Clicca su "Aggiungi Riga".
                    </td>
                  </tr>
                )}
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

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button 
            onClick={onBack}
            style={{ padding: '0.75rem 1.5rem', background: 'transparent', border: '1px solid var(--border)', color: 'white', borderRadius: '8px', cursor: 'pointer' }}
          >
            Annulla
          </button>
          <button 
            onClick={handleAcquire}
            disabled={saving}
            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.75rem 1.5rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold' }}
          >
            {saving ? <Loader2 size={20} className="spin" /> : <Save size={20} />}
            {saving ? 'Acquisizione...' : 'Acquisisci e Salva'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', textAlign: 'center' }}>
      <h1>Acquisisci Chiusure</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem' }}>
        Carica fino a 2 immagini del riepilogo cassa per estrarre automaticamente i dati.
      </p>

      {error && (
        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--danger)', padding: '1rem', borderRadius: '8px', color: 'var(--danger)', marginBottom: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
          <AlertCircle size={20} />
          {error}
        </div>
      )}

      <div 
        style={{ 
          border: '2px dashed var(--border)', 
          borderRadius: '12px', 
          padding: '3rem 2rem',
          background: 'rgba(255,255,255,0.02)',
          marginBottom: '2rem',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '1rem'
        }}
      >
        <Upload size={48} color="var(--accent)" />
        <h3 style={{ margin: 0 }}>Seleziona Immagini</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem', margin: 0 }}>PNG, JPG o JPEG (Max 2 file)</p>
        
        <input 
          type="file" 
          id="file-upload" 
          multiple 
          accept="image/*"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        <label 
          htmlFor="file-upload"
          style={{ padding: '0.75rem 1.5rem', background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'white', borderRadius: '8px', cursor: 'pointer', marginTop: '1rem' }}
        >
          Sfoglia File
        </label>
      </div>

      {files.length > 0 && (
        <div style={{ textAlign: 'left', marginBottom: '2rem' }}>
          <h4 style={{ marginBottom: '1rem' }}>File Selezionati ({files.length}/2):</h4>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {files.map((file, index) => (
              <div key={index} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-card)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <FileImage size={20} color="var(--accent)" />
                  <span style={{ fontSize: '0.875rem' }}>{file.name}</span>
                </div>
                <button 
                  onClick={() => handleRemoveFile(index)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <X size={18} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={handleExtract}
        disabled={files.length === 0 || loading}
        style={{
          width: '100%',
          padding: '1rem',
          background: files.length > 0 ? 'var(--accent)' : 'var(--bg-card)',
          color: files.length > 0 ? 'white' : 'var(--text-muted)',
          border: 'none',
          borderRadius: '8px',
          fontSize: '1rem',
          fontWeight: 'bold',
          cursor: files.length > 0 && !loading ? 'pointer' : 'not-allowed',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '0.5rem'
        }}
      >
        {loading && <Loader2 size={20} className="spin" />}
        {loading ? 'Estrazione in corso...' : 'Elabora e Mostra Anteprima'}
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '1.5rem 0' }}>
        <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
        <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>oppure</span>
        <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
      </div>

      <button
        onClick={handleManualEntry}
        style={{
          width: '100%',
          padding: '1rem',
          background: 'transparent',
          color: 'var(--text-main)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
          fontSize: '1rem',
          cursor: 'pointer',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '0.5rem'
        }}
      >
        <Plus size={20} />
        Inserimento Manuale
      </button>
    </div>
  );
}
