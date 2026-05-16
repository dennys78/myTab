import React, { useState, useEffect } from 'react';
import { Plus, Trash2, KeyRound, Loader2, Shield, User } from 'lucide-react';
import { useAuth } from './AuthContext';

export default function GestioneUtenti() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form nuovo utente
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('utente');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  // Cambio password
  const [changePwdId, setChangePwdId] = useState(null);
  const [changePwdValue, setChangePwdValue] = useState('');
  const [changingPwd, setChangingPwd] = useState(false);

  const fetchUsers = () => {
    setLoading(true);
    fetch('/api/users/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setUsers(d.data);
        else setError(d.error || 'Errore caricamento');
      })
      .catch(() => setError('Errore di rete'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleCreate = (e) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) return;
    setCreating(true);
    setCreateError(null);
    fetch('/api/users/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: newUsername.trim(), password: newPassword, role: newRole }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setNewUsername(''); setNewPassword(''); setNewRole('utente');
          fetchUsers();
        } else {
          setCreateError(d.error || 'Errore creazione');
        }
      })
      .catch(() => setCreateError('Errore di rete'))
      .finally(() => setCreating(false));
  };

  const handleDelete = (id, username) => {
    if (!window.confirm(`Eliminare l'utente "${username}"?`)) return;
    fetch(`/api/users/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchUsers(); })
      .catch(() => {});
  };

  const handleChangePassword = (id) => {
    if (!changePwdValue.trim()) return;
    setChangingPwd(true);
    fetch(`/api/users/${id}/change-password/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: changePwdValue }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') { setChangePwdId(null); setChangePwdValue(''); }
      })
      .catch(() => {})
      .finally(() => setChangingPwd(false));
  };

  const inp = { padding: '0.55rem 0.75rem', background: 'var(--bg-dark)', border: '1px solid var(--border)', color: 'white', borderRadius: '6px', fontSize: '0.9rem' };

  const RoleBadge = ({ role }) => (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
      padding: '0.2rem 0.6rem', borderRadius: '999px', fontSize: '0.75rem', fontWeight: 600,
      background: role === 'amministratore' ? 'rgba(59,130,246,0.15)' : 'rgba(148,163,184,0.1)',
      color: role === 'amministratore' ? 'var(--accent)' : 'var(--text-muted)',
      border: `1px solid ${role === 'amministratore' ? 'var(--accent)' : 'var(--border)'}`,
    }}>
      {role === 'amministratore' ? <Shield size={11} /> : <User size={11} />}
      {role === 'amministratore' ? 'Amministratore' : 'Utente'}
    </span>
  );

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Gestione Utenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Crea e gestisci gli operatori che accedono all'applicazione.
      </p>

      {/* Nuovo utente */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: '0 0 1.25rem', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Plus size={18} color="var(--accent)" /> Nuovo Operatore
        </h2>

        {createError && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.6rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.85rem' }}>
            {createError}
          </div>
        )}

        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Username</label>
              <input type="text" value={newUsername} onChange={e => setNewUsername(e.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} placeholder="mario.rossi" />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Password</label>
              <input type="password" value={newPassword} onChange={e => setNewPassword(e.target.value)} style={{ ...inp, width: '100%', boxSizing: 'border-box' }} placeholder="••••••••" />
            </div>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Ruolo</label>
            <select value={newRole} onChange={e => setNewRole(e.target.value)} style={{ ...inp, width: '200px' }}>
              <option value="utente">Utente</option>
              <option value="amministratore">Amministratore</option>
            </select>
          </div>
          <div>
            <button type="submit" disabled={creating || !newUsername.trim() || !newPassword.trim()}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.25rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}>
              {creating ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
              Crea Operatore
            </button>
          </div>
        </form>
      </div>

      {/* Lista utenti */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
        <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ margin: 0, fontSize: '1rem' }}>Operatori Registrati</h2>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : error ? (
          <div style={{ padding: '1.5rem', color: 'var(--danger)', fontSize: '0.9rem' }}>{error}</div>
        ) : users.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessun utente.</div>
        ) : (
          <div>
            {users.map((u, idx) => (
              <div key={u.id} style={{
                padding: '1rem 1.5rem',
                borderBottom: idx < users.length - 1 ? '1px solid var(--border)' : 'none',
                display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap',
              }}>
                <div style={{ flex: 1, minWidth: '120px' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.25rem' }}>
                    {u.username}
                    {u.id === me?.id && <span style={{ marginLeft: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>(tu)</span>}
                  </div>
                  <RoleBadge role={u.role} />
                </div>

                {/* Cambio password inline */}
                {changePwdId === u.id ? (
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <input
                      type="password"
                      value={changePwdValue}
                      onChange={e => setChangePwdValue(e.target.value)}
                      placeholder="Nuova password"
                      autoFocus
                      style={{ ...inp, width: '160px' }}
                    />
                    <button onClick={() => handleChangePassword(u.id)} disabled={changingPwd || !changePwdValue.trim()}
                      style={{ padding: '0.5rem 0.875rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                      {changingPwd ? <Loader2 size={14} className="spin" /> : 'Salva'}
                    </button>
                    <button onClick={() => { setChangePwdId(null); setChangePwdValue(''); }}
                      style={{ padding: '0.5rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                      Annulla
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button onClick={() => { setChangePwdId(u.id); setChangePwdValue(''); }}
                      title="Cambia password"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.4rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem' }}>
                      <KeyRound size={14} /> Password
                    </button>
                    <button
                      onClick={() => handleDelete(u.id, u.username)}
                      disabled={u.id === me?.id}
                      title={u.id === me?.id ? 'Non puoi eliminare te stesso' : 'Elimina utente'}
                      style={{ display: 'flex', alignItems: 'center', padding: '0.4rem 0.6rem', background: 'transparent', color: u.id === me?.id ? 'var(--border)' : 'var(--danger)', border: `1px solid ${u.id === me?.id ? 'var(--border)' : 'var(--danger)'}`, borderRadius: '6px', cursor: u.id === me?.id ? 'not-allowed' : 'pointer' }}>
                      <Trash2 size={15} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
