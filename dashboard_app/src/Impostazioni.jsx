import { useState, useEffect } from 'react';
import { Save, Loader2, CheckCircle, AlertCircle, Eye, EyeOff, Zap, Wallet, PiggyBank, Send, RotateCcw } from 'lucide-react';
import { apiFetch } from './api';

export default function Impostazioni() {
  const [groqKey, setGroqKey] = useState('');
  const [keyConfigured, setKeyConfigured] = useState(false);
  const [showKey, setShowKey] = useState(false);
  const [telegramToken, setTelegramToken] = useState('');
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [showTelegramToken, setShowTelegramToken] = useState(false);
  const [savingTelegram, setSavingTelegram] = useState(false);
  const [telegramSaved, setTelegramSaved] = useState(false);
  const [resettingTelegram, setResettingTelegram] = useState(false);
  const [telegramResetResult, setTelegramResetResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);
  const [saldoCassa, setSaldoCassa] = useState('');
  const [fondoCassa, setFondoCassa] = useState('');
  const [savingBalances, setSavingBalances] = useState(false);
  const [balancesSaved, setBalancesSaved] = useState(false);

  useEffect(() => {
    apiFetch('/api/settings/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setKeyConfigured(d.data.groq_key_configured);
          setTelegramConfigured(d.data.telegram_token_configured);
          setSaldoCassa(Number(d.data.saldo_cassa ?? 0).toFixed(2));
          setFondoCassa(Number(d.data.fondo_cassa ?? 0).toFixed(2));
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = () => {
    if (!groqKey.trim()) return;
    setSaving(true);
    setError(null);
    setSaved(false);

    apiFetch('/api/settings/save/', {
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
        Configura le integrazioni esterne utilizzate dall'applicazione.
      </p>

      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '16px', padding: '1.5rem', marginBottom: '1.5rem' }}>
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
