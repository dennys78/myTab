import { useState, useEffect } from 'react';
import { Save, Loader2, CheckCircle, AlertCircle, Eye, EyeOff, Zap, Wallet, PiggyBank, Send, RotateCcw, Trash2, Building2 } from 'lucide-react';
import { apiFetch } from './api';

export default function Impostazioni() {
  const [groqKey, setGroqKey] = useState('');
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [geminiKey, setGeminiKey] = useState('');
  const [geminiConfigured, setGeminiConfigured] = useState(false);
  const [showGeminiKey, setShowGeminiKey] = useState(false);
  const [aiProvider, setAiProvider] = useState('groq');
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [showTelegramToken, setShowTelegramToken] = useState(false);
  const [savingTelegram, setSavingTelegram] = useState(false);
  const [telegramSaved, setTelegramSaved] = useState(false);
  const [resettingTelegram, setResettingTelegram] = useState(false);
  const [telegramResetResult, setTelegramResetResult] = useState(null);
  const [restartingTelegramBot, setRestartingTelegramBot] = useState(false);
  const [telegramBotRestarted, setTelegramBotRestarted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [saldoCassa, setSaldoCassa] = useState('');
  const [fondoCassa, setFondoCassa] = useState('');
  const [savingBalances, setSavingBalances] = useState(false);
  const [balancesSaved, setBalancesSaved] = useState(false);
  const [imagePurgeScope, setImagePurgeScope] = useState('month');
  const [imagePurgeMonth, setImagePurgeMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const [purgingImages, setPurgingImages] = useState(false);
  const [imagePurgeResult, setImagePurgeResult] = useState(null);

  const [denominazione, setDenominazione] = useState('');
  const [indirizzo, setIndirizzo] = useState('');
  const [piva, setPiva] = useState('');
  const [companies, setCompanies] = useState([]);
  const [activeCompanyId, setActiveCompanyId] = useState(null);
  const [savingCompany, setSavingCompany] = useState(false);
  const [companySaved, setCompanySaved] = useState(false);
  const [newCompanyName, setNewCompanyName] = useState('');

  useEffect(() => {
    apiFetch('/api/settings/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setKeyConfigured(d.data.groq_key_configured);
          setGeminiConfigured(d.data.gemini_key_configured);
          setAiProvider(d.data.ai_acquisition_provider || 'groq');
          setTelegramConfigured(d.data.telegram_token_configured);
          setSaldoCassa(Number(d.data.saldo_cassa ?? 0).toFixed(2));
          setFondoCassa(Number(d.data.fondo_cassa ?? 0).toFixed(2));
          setDenominazione(d.data.denominazione || '');
          setIndirizzo(d.data.indirizzo || '');
          setPiva(d.data.piva || '');
          setCompanies(d.data.companies || []);
          setActiveCompanyId(d.data.active_company_id || null);
        }
      })
      .catch(() => {});
  }, []);

  const handleSwitchCompany = (companyId) => {
    if (!companyId || Number(companyId) === Number(activeCompanyId)) return;
    setError(null);
    apiFetch('/api/companies/switch/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: Number(companyId) }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          window.location.reload();
        } else {
          setError(d.error || 'Errore cambio azienda.');
        }
      })
      .catch(() => setError('Errore di rete.'));
  };

  const handleSaveCompany = () => {
    if (!denominazione.trim()) {
      setError('La denominazione aziendale è obbligatoria.');
      return;
    }
    setSavingCompany(true);
    setError(null);
    setCompanySaved(false);
    apiFetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        denominazione: denominazione.trim(),
        indirizzo: indirizzo.trim(),
        piva: piva.trim(),
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setCompanySaved(true);
          setDenominazione(d.data.denominazione || '');
          setIndirizzo(d.data.indirizzo || '');
          setPiva(d.data.piva || '');
          setCompanies(d.data.companies || []);
          setActiveCompanyId(d.data.active_company_id || null);
          setTimeout(() => setCompanySaved(false), 3000);
        } else {
          setError(d.error || 'Errore salvataggio dati azienda.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSavingCompany(false));
  };

  const handleCreateCompany = () => {
    const name = newCompanyName.trim();
    if (!name) return;
    setSavingCompany(true);
    setError(null);
    apiFetch('/api/companies/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ denominazione: name }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setNewCompanyName('');
          window.location.reload();
        } else {
          setError(d.error || 'Errore creazione azienda.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSavingCompany(false));
  };

  const handleSave = () => {
    setSaving(true);
    setError(null);
    setSaved(false);

    const payload = { ai_acquisition_provider: aiProvider };
    if (groqKey.trim()) payload.groq_api_key = groqKey.trim();
    if (geminiKey.trim()) payload.gemini_api_key = geminiKey.trim();

    apiFetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setSaved(true);
          if (groqKey.trim()) setKeyConfigured(true);
          if (geminiKey.trim()) setGeminiConfigured(true);
          setGroqKey('');
          setGeminiKey('');
          setTimeout(() => setSaved(false), 3000);
        } else {
          setError(d.error || 'Errore durante il salvataggio.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSaving(false));
  };

  const handleSaveTelegram = () => {
    if (!telegramToken.trim()) return;
    setSavingTelegram(true);
    setError(null);
    setTelegramSaved(false);

    apiFetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ telegram_bot_token: telegramToken.trim() }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setTelegramSaved(true);
          setTelegramConfigured(true);
          setTelegramToken('');
          setTimeout(() => setTelegramSaved(false), 3000);
        } else {
          setError(d.error || 'Errore durante il salvataggio del token Telegram.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSavingTelegram(false));
  };

  const handleResetTelegramSessions = () => {
    setResettingTelegram(true);
    setTelegramResetResult(null);
    setError(null);

    apiFetch('/api/settings/telegram/reset-sessions/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setTelegramResetResult(d.data);
          setTimeout(() => setTelegramResetResult(null), 6000);
        } else {
          setError(d.error || 'Errore durante il reset delle sessioni Telegram.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setResettingTelegram(false));
  };

  const handleRestartTelegramBot = () => {
    setRestartingTelegramBot(true);
    setTelegramBotRestarted(false);
    setError(null);

    apiFetch('/api/settings/telegram/restart-bot/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setTelegramBotRestarted(true);
          setTimeout(() => setTelegramBotRestarted(false), 6000);
        } else {
          setError(d.error || 'Errore durante il riavvio del bot Telegram.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setRestartingTelegramBot(false));
  };

  const handleSaveBalances = () => {
    setSavingBalances(true);
    setError(null);
    setBalancesSaved(false);

    apiFetch('/api/settings/save/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        saldo_cassa: parseFloat(saldoCassa) || 0,
        fondo_cassa: parseFloat(fondoCassa) || 0,
      }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setSaldoCassa(Number(d.data.saldo_cassa ?? 0).toFixed(2));
          setFondoCassa(Number(d.data.fondo_cassa ?? 0).toFixed(2));
          setBalancesSaved(true);
          setTimeout(() => setBalancesSaved(false), 3000);
        } else {
          setError(d.error || 'Errore durante il salvataggio dei valori.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setSavingBalances(false));
  };

  const handlePurgeImages = () => {
    const label = imagePurgeScope === 'all' ? 'tutte le immagini archiviate' : `le immagini del mese ${imagePurgeMonth}`;
    if (!window.confirm(`Eliminare ${label}? L'operazione non è reversibile.`)) return;
    setPurgingImages(true);
    setImagePurgeResult(null);
    setError(null);

    apiFetch('/api/settings/images/purge/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope: imagePurgeScope, month: imagePurgeMonth }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setImagePurgeResult(d.data);
          setTimeout(() => setImagePurgeResult(null), 8000);
        } else {
          setError(d.error || 'Errore durante eliminazione immagini.');
        }
      })
      .catch(() => setError('Errore di rete.'))
      .finally(() => setPurgingImages(false));
  };

  const inputStyle = {
    flex: 1,
    padding: '0.6rem 0.75rem',
    background: 'var(--bg-elevated)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '10px',
    fontSize: '0.9rem',
    fontFamily: 'monospace',
  };

  return (
    <div style={{ maxWidth: '760px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Impostazioni</h1>
      <p style={{ color: 'var(--text-muted)', marginBottom: '2rem', fontSize: '0.9rem' }}>
        Configura i dati aziendali e le integrazioni esterne utilizzate dall'applicazione.
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.6rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
          <AlertCircle size={15} /> {error}
        </div>
      )}

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Building2 size={20} color="var(--accent)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Dati aziendali</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Ogni azienda ha chiusure, versamenti e impostazioni separate. I dati qui sotto riguardano l&apos;azienda attiva.
        </p>

        {companies.length > 1 && (
          <div style={{ marginBottom: '1rem' }}>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Azienda attiva</label>
            <select
              value={activeCompanyId || ''}
              onChange={(e) => handleSwitchCompany(e.target.value)}
              style={{ ...inputStyle, width: '100%', maxWidth: '420px', fontFamily: 'inherit' }}
            >
              {companies.map(c => (
                <option key={c.id} value={c.id}>{c.denominazione || `Azienda #${c.id}`}</option>
              ))}
            </select>
          </div>
        )}

        <div style={{ display: 'grid', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Denominazione *</label>
            <input type="text" value={denominazione} onChange={e => setDenominazione(e.target.value)} style={{ ...inputStyle, fontFamily: 'inherit', width: '100%' }} placeholder="es. Tabaccheria Rossi" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Indirizzo</label>
            <textarea value={indirizzo} onChange={e => setIndirizzo(e.target.value)} rows={2} style={{ ...inputStyle, fontFamily: 'inherit', width: '100%', resize: 'vertical' }} placeholder="Via, CAP, Città" />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>PIVA</label>
            <input type="text" value={piva} onChange={e => setPiva(e.target.value)} style={{ ...inputStyle, fontFamily: 'inherit', width: '100%', maxWidth: '280px' }} placeholder="IT12345678901" />
          </div>
        </div>

        {companySaved && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '6px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Dati aziendali salvati.
          </div>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
          <button
            onClick={handleSaveCompany}
            disabled={savingCompany}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}
          >
            {savingCompany ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Salva dati azienda
          </button>
          <input
            type="text"
            value={newCompanyName}
            onChange={e => setNewCompanyName(e.target.value)}
            placeholder="Nuova azienda..."
            style={{ ...inputStyle, fontFamily: 'inherit', minWidth: '180px', flex: '1 1 180px' }}
          />
          <button
            type="button"
            onClick={handleCreateCompany}
            disabled={savingCompany || !newCompanyName.trim()}
            style={{ padding: '0.6rem 1rem', background: 'transparent', color: 'var(--text-main)', border: '1px solid var(--border)', borderRadius: '6px', cursor: newCompanyName.trim() ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: '0.9rem' }}
          >
            Aggiungi azienda
          </button>
        </div>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Zap size={20} color="var(--accent)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Acquisizione IA</h2>
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.3rem', color: 'var(--accent)', fontSize: '0.8rem', fontWeight: 600 }}>
            Provider attivo: {aiProvider === 'gemini' ? 'Gemini' : 'Groq'}
          </span>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Scegli il motore usato da "Acquisisci con IA". Groq usa Llama 4 Scout Vision; Gemini usa gemini-2.0-flash, economico e adatto alle immagini.
        </p>

        {saved && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '6px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Impostazioni IA salvate correttamente.
          </div>
        )}

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Modello acquisizione attivo
          </label>
          <select value={aiProvider} onChange={e => setAiProvider(e.target.value)} style={{ ...inputStyle, width: '260px', fontFamily: 'inherit' }}>
            <option value="groq">Groq - Llama 4 Scout Vision</option>
            <option value="gemini">Gemini - gemini-2.0-flash</option>
          </select>
        </div>

        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          {keyConfigured ? 'Chiave API Groq configurata - inseriscine una nuova per sostituirla' : 'Chiave API Groq'}
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '0.9rem' }}>
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
          {keyConfigured && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#22c55e', fontSize: '0.8rem', fontWeight: 600 }}>
              <CheckCircle size={14} /> Configurata
            </span>
          )}
        </div>

        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          {geminiConfigured ? 'Chiave API Gemini configurata - inseriscine una nuova per sostituirla' : 'Chiave API Gemini'}
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginBottom: '1rem' }}>
          <input
            type={showGeminiKey ? 'text' : 'password'}
            value={geminiKey}
            onChange={e => setGeminiKey(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
            placeholder="AIza..."
            style={inputStyle}
          />
          <button
            onClick={() => setShowGeminiKey(v => !v)}
            title={showGeminiKey ? 'Nascondi' : 'Mostra'}
            style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', padding: '0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            {showGeminiKey ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
          {geminiConfigured && (
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#22c55e', fontSize: '0.8rem', fontWeight: 600 }}>
              <CheckCircle size={14} /> Configurata
            </span>
          )}
        </div>

        <div>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}
          >
            {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Salva impostazioni IA
          </button>
        </div>

        <div style={{ marginTop: '1rem', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border)', background: 'rgba(8,17,31,0.35)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontWeight: 700, marginBottom: '0.2rem' }}>Reset sessioni Telegram</div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: 0 }}>
                Azzera eventuali acquisizioni rimaste in sospeso nel bot. Le bozze già create in myTab non vengono eliminate.
              </p>
            </div>
            <button
              onClick={handleResetTelegramSessions}
              disabled={resettingTelegram || !telegramConfigured}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1rem', background: telegramConfigured ? 'rgba(245,158,11,0.14)' : 'var(--bg-dark)', color: telegramConfigured ? 'var(--warning)' : 'var(--text-muted)', border: `1px solid ${telegramConfigured ? 'var(--warning)' : 'var(--border)'}`, borderRadius: '10px', cursor: telegramConfigured ? 'pointer' : 'not-allowed', fontWeight: 700, fontSize: '0.88rem' }}
            >
              {resettingTelegram ? <Loader2 size={16} className="spin" /> : <RotateCcw size={16} />}
              Reset sessioni
            </button>
          </div>
          {telegramResetResult && (
            <div style={{ marginTop: '0.85rem', background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '8px', color: '#22c55e', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
              <CheckCircle size={15} />
              Sessioni azzerate. Conferme Telegram inviate: {telegramResetResult.telegram_messages_sent}/{telegramResetResult.known_chats}.
            </div>
          )}
        </div>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Send size={20} color="var(--accent)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Telegram Bot</h2>
          {telegramConfigured && (
            <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.3rem', color: '#22c55e', fontSize: '0.8rem', fontWeight: 600 }}>
              <CheckCircle size={14} /> Configurato
            </span>
          )}
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Token del bot Telegram usato per acquisire chiusure cassa tramite foto. Il valore non viene mostrato dopo il salvataggio.
        </p>

        {telegramSaved && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '6px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Token Telegram salvato correttamente.
          </div>
        )}
        {telegramBotRestarted && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '6px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Riavvio bot richiesto. Il servizio Docker ripartirà con il token aggiornato.
          </div>
        )}

        <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
          {telegramConfigured ? 'Inserisci un nuovo token per sostituire quello esistente' : 'Token bot Telegram'}
        </label>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <input
            type={showTelegramToken ? 'text' : 'password'}
            value={telegramToken}
            onChange={e => setTelegramToken(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSaveTelegram()}
            placeholder="1234567890:AA..."
            style={inputStyle}
          />
          <button
            onClick={() => setShowTelegramToken(v => !v)}
            title={showTelegramToken ? 'Nascondi' : 'Mostra'}
            style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', padding: '0.6rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
          >
            {showTelegramToken ? <EyeOff size={17} /> : <Eye size={17} />}
          </button>
          <button
            onClick={handleSaveTelegram}
            disabled={savingTelegram || !telegramToken.trim()}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.1rem', background: telegramToken.trim() ? 'var(--accent)' : 'var(--bg-dark)', color: telegramToken.trim() ? 'white' : 'var(--text-muted)', border: 'none', borderRadius: '6px', cursor: telegramToken.trim() ? 'pointer' : 'not-allowed', fontWeight: 600, fontSize: '0.9rem' }}
          >
            {savingTelegram ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
            Salva
          </button>
        </div>

        <div style={{ marginTop: '1rem', padding: '1rem', borderRadius: '12px', border: '1px solid var(--border)', background: 'rgba(8,17,31,0.35)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontWeight: 700, marginBottom: '0.2rem' }}>Riavvia bot Telegram</div>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', margin: 0 }}>
                Usa questo comando dopo aver sostituito il token. Il bot Docker si riavvia e legge la nuova configurazione.
              </p>
            </div>
            <button
              onClick={handleRestartTelegramBot}
              disabled={restartingTelegramBot || !telegramConfigured}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.65rem 1rem', background: telegramConfigured ? 'rgba(79,141,247,0.14)' : 'var(--bg-dark)', color: telegramConfigured ? 'var(--accent)' : 'var(--text-muted)', border: `1px solid ${telegramConfigured ? 'var(--accent)' : 'var(--border)'}`, borderRadius: '10px', cursor: telegramConfigured ? 'pointer' : 'not-allowed', fontWeight: 700, fontSize: '0.88rem' }}
            >
              {restartingTelegramBot ? <Loader2 size={16} className="spin" /> : <RotateCcw size={16} />}
              Riavvia bot
            </button>
          </div>
        </div>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Trash2 size={20} color="var(--danger)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Archivio Immagini Incassi</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Elimina immagini archiviate su disco. I dati contabili restano salvati, ma le foto associate non saranno più disponibili.
        </p>

        {imagePurgeResult && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '8px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Eliminate {imagePurgeResult.total_deleted} immagini.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', alignItems: 'end', marginBottom: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Ambito</label>
            <select value={imagePurgeScope} onChange={e => setImagePurgeScope(e.target.value)} style={{ ...inputStyle, width: '100%', fontFamily: 'inherit' }}>
              <option value="month">Un mese specifico</option>
              <option value="all">Tutte le immagini</option>
            </select>
          </div>
          {imagePurgeScope === 'month' && (
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Mese</label>
              <input type="month" value={imagePurgeMonth} onChange={e => setImagePurgeMonth(e.target.value)} style={{ ...inputStyle, width: '100%', fontFamily: 'inherit' }} />
            </div>
          )}
        </div>

        <button
          onClick={handlePurgeImages}
          disabled={purgingImages || (imagePurgeScope === 'month' && !imagePurgeMonth)}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.7rem 1.15rem', background: 'transparent', color: 'var(--danger)', border: '1px solid var(--danger)', borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '0.9rem' }}
        >
          {purgingImages ? <Loader2 size={16} className="spin" /> : <Trash2 size={16} />}
          Elimina immagini
        </button>
      </div>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem' }}>
          <Wallet size={20} color="var(--accent)" />
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>Rettifiche Cassa</h2>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.25rem' }}>
          Modifica questi valori solo per allineare myTab alla cassa reale. Le rettifiche sono riservate agli amministratori.
        </p>

        {balancesSaved && (
          <div style={{ background: 'rgba(34,197,94,0.1)', border: '1px solid #22c55e', padding: '0.6rem 0.9rem', borderRadius: '8px', color: '#22c55e', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
            <CheckCircle size={15} /> Valori cassa aggiornati correttamente.
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              <Wallet size={14} /> Contanti in Cassa
            </label>
            <input
              type="number"
              step="0.01"
              value={saldoCassa}
              onChange={e => setSaldoCassa(e.target.value)}
              style={{ ...inputStyle, width: '100%' }}
            />
          </div>
          <div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              <PiggyBank size={14} /> Fondo Cassa
            </label>
            <input
              type="number"
              step="0.01"
              value={fondoCassa}
              onChange={e => setFondoCassa(e.target.value)}
              style={{ ...inputStyle, width: '100%' }}
            />
          </div>
        </div>

        <button
          onClick={handleSaveBalances}
          disabled={savingBalances}
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.7rem 1.15rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '10px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}
        >
          {savingBalances ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
          Salva Rettifiche
        </button>
      </div>
    </div>
  );
}
