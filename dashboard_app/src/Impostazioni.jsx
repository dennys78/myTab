import React, { useState, useEffect } from 'react';
import { Save, Loader2, CheckCircle, AlertCircle, Eye, EyeOff, Zap } from 'lucide-react';

export default function Impostazioni() {
  const [groqKey, setGroqKey] = useState('');
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('/api/settings/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setKeyConfigured(d.data.groq_key_configured);
      })
      .catch(() => {});
  }, []);

  const handleSave = () => {
    if (!groqKey.trim()) return;
    setSaving(true);
    setError(null);
    setSaved(false);

    fetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groq_api_key: groqKey.trim() }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setSaved(true);
          setKeyConfigured(true);
          setGroqKey('');
          setTimeout(() => setSaved(false), 3000);
        } else {
          setError(d.error || 'Errore durante il salvataggio.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const inputStyle = {
    flex: 1,
    padding: '0.6rem 0.75rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.9rem',
    fontFamily: 'monospace',
  };

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Impostazioni</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        Configura le integrazioni esterne utilizzate dall'applicazione.
      </p>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Zap size={20} color="var(--accent)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Groq — IA Vision</h2>
          {keyConfigured && (
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#22c55e', fontSize: '0.8rem', fontWeight: 600 }}>
              <CheckCircle size={14} /> Configurata
            </span>
          )}
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Usata da "Acquisisci con IA" (modello Llama 4 Scout Vision). Gratuita fino a 14.400 richieste/giorno.
          Ottienila su <span style={{ color: 'var(--accent)' }}>console.groq.com</span>.
        </p>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.6rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <AlertCircle size={15} /> {error}
          </div>
        )}

        {saved && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '6px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Chiave salvata correttamente.
          </div>
        )}

        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          {keyConfigured ? 'Inserisci una nuova chiave per sostituire quella esistente' : 'Chiave API Groq'}
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type={showKey ? 'text' : 'password'}
            value={groqKey}
            onChange={e => setGroqKey(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
            placeholder="gsk_..."
            style={inputStyle}
          />
          <button
            onClick={() => setShowKey(v => !v)}
            title={showKey ? 'Nascondi' : 'Mostra'}
            style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', padding: '0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            {showKey ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !groqKey.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem', background: groqKey.trim() ? 'var(--accent)' : 'var(--bg-dark)', color: groqKey.trim() ? 'white' : 'var(--text-muted)', border: 'none', borderRadius: '6px', cursor: groqKey.trim() ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: '0.9rem' }}
          >
            {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Salva
          </button>
        </div>
      </div>
    </div>
  );
}
