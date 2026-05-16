import React, { useState } from 'react';
import { Upload, FileImage, Calculator, Save, AlertCircle, Loader2, X, Plus } from 'lucide-react';

export default function AcquisisciChiusure({ onBack }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [saving, setSaving] = useState(false);

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

    fetch('/api/closures/extract/', {
      method: 'POST',
      body: formData,
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          // Initialize IDs for items to edit them easily
          const dataWithIds = {
            ...data.data,
            items: data.data.items.map((item, i) => ({ ...item, id: `temp_${i}` }))
          };
          if (!dataWithIds.date) {
            dataWithIds.date = new Date().toISOString().split('T')[0];
          }
          setPreviewData(dataWithIds);
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
    setPreviewData(prev => ({
      ...prev,
      summary: {
        ...prev.summary,
        [name]: parseFloat(value) || 0
      }
    }));
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
      items: prev.items.map(item => 
        item.id === id ? { ...item, [field]: field === 'descrizione' ? value : (parseFloat(value) || 0) } : item
      )
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

  const handleAcquire = () => {
    setSaving(true);
    setError(null);
    
    // Remove temporary IDs
    const payload = {
      date: previewData.date,
      operator: 'Web Dashboard',
      summary: previewData.summary,
      items: previewData.items.map(({ id, ...rest }) => rest)
    };

    fetch('/api/closures/insert/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success' || data.id) {
          alert("Acquisizione completata con successo!");
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

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
            {Object.keys(previewData.summary).map(key => (
              <div key={key}>
                <label style={{ display: 'block', fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'capitalize' }}>
                  {key.replace('_', ' ')}
                </label>
                <input 
                  type="number" 
                  name={key}
                  value={previewData.summary[key] === 0 ? '' : previewData.summary[key]} 
                  onChange={handleInputChange}
                  placeholder="0.00"
                  style={{ width: '100%', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                />
              </div>
            ))}
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
                        type="text" 
                        value={item.descrizione} 
                        onChange={(e) => handleItemChange(item.id, 'descrizione', e.target.value)}
                        placeholder="Nome Reparto"
                        style={{ width: '100%', minWidth: '150px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={item.entrate === 0 ? '' : item.entrate} 
                        onChange={(e) => handleItemChange(item.id, 'entrate', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={item.uscite === 0 ? '' : item.uscite} 
                        onChange={(e) => handleItemChange(item.id, 'uscite', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
                    </td>
                    <td>
                      <input 
                        type="number" 
                        value={item.saldo === 0 ? '' : item.saldo} 
                        onChange={(e) => handleItemChange(item.id, 'saldo', e.target.value)}
                        placeholder="0.00"
                        style={{ width: '100px', padding: '0.5rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px' }}
                      />
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
    </div>
  );
}
