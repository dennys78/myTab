import { useState } from 'react';
import { Cigarette, Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import InstallPwa from './InstallPwa';

export default function Login() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) return;
    setLoading(true);
    setError(null);
    apiFetch('/api/auth/login/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.trim(), password }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') login(d.data);
        else setError(d.error || 'Credenziali non valide');
      })
      .catch(() => setError('Errore di rete'))
      .finally(() => setLoading(false));
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg-dark)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
    }}>
      <div style={{ width: '100%', maxWidth: '420px' }}>
        <InstallPwa />
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '16px',
        padding: '2.5rem 2rem',
        width: '100%',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.55rem', marginBottom: '0.5rem' }}>
            <Cigarette size={40} color="var(--accent)" />
            <span style={{ fontSize: '2.1rem', fontWeight: '700', color: 'var(--text-main)' }}>myTab</span>
          </div>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', margin: 0 }}>
            Gestione Chiusure Cassa
          </p>
        </div>

        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid var(--danger)',
            padding: '0.7rem 1rem',
            borderRadius: '8px',
            color: 'var(--danger)',
            marginBottom: '1.25rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.875rem',
          }}>
            <AlertCircle size={16} /> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoComplete="username"
              autoFocus
              style={{
                width: '100%',
                padding: '0.7rem 0.875rem',
                background: 'var(--bg-dark)',
                border: '1px solid var(--border)',
                color: 'white',
                borderRadius: '8px',
                fontSize: '1rem',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
              Password
            </label>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <input
                type={showPwd ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                style={{
                  flex: 1,
                  padding: '0.7rem 0.875rem',
                  background: 'var(--bg-dark)',
                  border: '1px solid var(--border)',
                  color: 'white',
                  borderRadius: '8px',
                  fontSize: '1rem',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPwd(v => !v)}
                style={{ background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '8px', padding: '0 0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
              >
                {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            style={{
              padding: '0.85rem',
              background: username.trim() && password.trim() ? 'var(--accent)' : 'var(--bg-dark)',
              color: username.trim() && password.trim() ? 'white' : 'var(--text-muted)',
              border: 'none',
              borderRadius: '8px',
              fontSize: '1rem',
              fontWeight: '600',
              cursor: username.trim() && password.trim() && !loading ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              marginTop: '0.5rem',
            }}
          >
            {loading ? <><Loader2 size={18} className="spin" /> Accesso...</> : 'Accedi'}
          </button>
        </form>
      </div>
      </div>
    </div>
  );
}
