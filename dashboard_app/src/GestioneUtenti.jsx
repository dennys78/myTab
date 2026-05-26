import { useCallback, useEffect, useState } from 'react';
import { Plus, Trash2, Pencil, Loader2, Shield, User, Building2 } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';

export default function GestioneUtenti() {
  const { user: me } = useAuth();
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState('utente');
  const [newCompanyId, setNewCompanyId] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState(null);

  const [editUserId, setEditUserId] = useState(null);
  const [editUsername, setEditUsername] = useState('');
  const [editPassword, setEditPassword] = useState('');
  const [editRole, setEditRole] = useState('utente');
  const [editCompanyId, setEditCompanyId] = useState('');
  const [updatingUser, setUpdatingUser] = useState(false);
  const [editError, setEditError] = useState(null);

  const fetchCompanies = useCallback(() => {
    apiFetch('/api/companies/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          const list = d.data || [];
          setCompanies(list);
          setNewCompanyId(prev => prev || (list[0]?.id ? String(list[0].id) : ''));
        }
      })
      .catch(() => {});
  }, []);

  const fetchUsers = useCallback((showLoading = true) => {
    if (showLoading) setLoading(true);
    apiFetch('/api/users/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setUsers(d.data);
        else setError(d.error || 'Errore caricamento');
      })
      .catch(() => setError('Errore di rete'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchCompanies();
    const timer = window.setTimeout(() => fetchUsers(false), 0);
    return () => window.clearTimeout(timer);
  }, [fetchCompanies, fetchUsers]);

  const handleCreate = (e) => {
    e.preventDefault();
    if (!newUsername.trim() || !newPassword.trim()) return;
    if (newRole === 'utente' && !newCompanyId) {
      setCreateError('Seleziona un\'azienda per l\'operatore.');
      return;
    }
    setCreating(true);
    setCreateError(null);
    const payload = {
      username: newUsername.trim(),
      password: newPassword,
      role: newRole,
    };
    if (newRole === 'utente') payload.company_id = Number(newCompanyId);

    apiFetch('/api/users/create/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setNewUsername('');
          setNewPassword('');
          setNewRole('utente');
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
    apiFetch(`/api/users/${id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => { if (d.status === 'success') fetchUsers(); })
      .catch(() => {});
  };

  const startEditUser = (u) => {
    setEditUserId(u.id);
    setEditUsername(u.username);
    setEditPassword('');
    setEditRole(u.role);
    setEditCompanyId(u.assigned_company?.id ? String(u.assigned_company.id) : (companies[0]?.id ? String(companies[0].id) : ''));
    setEditError(null);
  };

  const cancelEditUser = () => {
    setEditUserId(null);
    setEditUsername('');
    setEditPassword('');
    setEditRole('utente');
    setEditCompanyId('');
    setEditError(null);
  };

  const handleUpdateUser = (id) => {
    if (!editUsername.trim()) return;
    if (editRole === 'utente' && !editCompanyId) {
      setEditError('Seleziona un\'azienda per l\'operatore.');
      return;
    }
    setUpdatingUser(true);
    setEditError(null);
    const payload = {
      username: editUsername.trim(),
      password: editPassword,
      role: editRole,
    };
    if (editRole === 'utente') payload.company_id = Number(editCompanyId);

    apiFetch(`/api/users/${id}/update/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          cancelEditUser();
          fetchUsers();
        } else {
          setEditError(d.error || 'Errore aggiornamento utente');
        }
      })
      .catch(() => setEditError('Errore di rete'))
      .finally(() => setUpdatingUser(false));
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

  const CompanySelect = ({ value, onChange, id }) => (
    <select id={id} value={value} onChange={onChange} style={{ ...inp, width: '100%' }}>
      <option value="">Seleziona azienda...</option>
      {companies.map(c => (
        <option key={c.id} value={c.id}>{c.denominazione || `Azienda #${c.id}`}</option>
      ))}
    </select>
  );

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Gestione Utenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '2rem' }}>
        Crea operatori associati a un&apos;azienda. Gli amministratori possono vedere tutte le aziende e selezionare quella attiva.
      </p>

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
          <div style={{ display: 'grid', gridTemplateColumns: '200px 1fr', gap: '0.75rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Ruolo</label>
              <select value={newRole} onChange={e => setNewRole(e.target.value)} style={{ ...inp, width: '100%' }}>
                <option value="utente">Utente</option>
                <option value="amministratore">Amministratore</option>
              </select>
            </div>
            {newRole === 'utente' && (
              <div>
                <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Azienda *</label>
                <CompanySelect value={newCompanyId} onChange={e => setNewCompanyId(e.target.value)} />
              </div>
            )}
          </div>
          <div>
            <button type="submit" disabled={creating || !newUsername.trim() || !newPassword.trim() || (newRole === 'utente' && !newCompanyId)}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.6rem 1.25rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem' }}>
              {creating ? <Loader2 size={16} className="spin" /> : <Plus size={16} />}
              Crea Operatore
            </button>
          </div>
        </form>
      </div>

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
                <div style={{ flex: 1, minWidth: '160px' }}>
                  <div style={{ fontWeight: 600, fontSize: '0.95rem', marginBottom: '0.25rem' }}>
                    {editUserId === u.id ? 'Modifica operatore' : u.username}
                    {u.id === me?.id && editUserId !== u.id && <span style={{ marginLeft: '0.5rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>(tu)</span>}
                  </div>
                  {editUserId === u.id ? (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.5rem', alignItems: 'end' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Username</label>
                        <input type="text" value={editUsername} onChange={e => setEditUsername(e.target.value)} autoFocus style={{ ...inp, width: '100%' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Nuova password</label>
                        <input type="password" value={editPassword} onChange={e => setEditPassword(e.target.value)} placeholder="Lascia vuoto per non cambiarla" style={{ ...inp, width: '100%' }} />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Ruolo</label>
                        <select value={editRole} onChange={e => setEditRole(e.target.value)} style={{ ...inp, width: '100%' }}>
                          <option value="utente">Utente</option>
                          <option value="amministratore">Amministratore</option>
                        </select>
                      </div>
                      {editRole === 'utente' && (
                        <div>
                          <label style={{ display: 'block', fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Azienda *</label>
                          <CompanySelect value={editCompanyId} onChange={e => setEditCompanyId(e.target.value)} />
                        </div>
                      )}
                      {editError && (
                        <div style={{ gridColumn: '1 / -1', color: 'var(--danger)', fontSize: '0.82rem' }}>
                          {editError}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                      <RoleBadge role={u.role} />
                      {u.role === 'utente' && u.assigned_company && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <Building2 size={12} /> {u.assigned_company.denominazione}
                        </span>
                      )}
                      {u.role === 'amministratore' && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Tutte le aziende</span>
                      )}
                    </div>
                  )}
                </div>

                {editUserId === u.id ? (
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button onClick={() => handleUpdateUser(u.id)} disabled={updatingUser || !editUsername.trim()}
                      style={{ padding: '0.5rem 0.875rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                      {updatingUser ? <Loader2 size={14} className="spin" /> : 'Salva'}
                    </button>
                    <button onClick={cancelEditUser}
                      style={{ padding: '0.5rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
                      Annulla
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button onClick={() => startEditUser(u)}
                      title="Modifica username, password, ruolo e azienda"
                      style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.4rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.8rem' }}>
                      <Pencil size={14} /> Modifica
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
