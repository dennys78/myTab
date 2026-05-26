import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Plus, Trash2, Pencil, Loader2, Shield, User, Building2, Save, X, Menu,
} from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import { SIDEBAR_ITEMS, getDefaultSidebarMenu, getVisibleNavItems, normalizeSidebarMenu } from './navConfig';

const EMPTY_FORM = {
  username: '',
  password: '',
  role: 'utente',
  companyId: '',
  sidebarMenu: [],
};

export default function GestioneUtenti() {
  const { user: me, refreshUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [selectedUserId, setSelectedUserId] = useState(null);
  const [panelMode, setPanelMode] = useState(null); // null | 'new' | 'edit'
  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

  const selectedUser = useMemo(
    () => users.find(u => u.id === selectedUserId) || null,
    [users, selectedUserId],
  );


  const visibleNavItems = useMemo(
    () => getVisibleNavItems(form.role, form.sidebarMenu),
    [form.role, form.sidebarMenu],
  );

  const toggleMenuItem = (itemId) => {
    setForm(f => {
      const selected = new Set(f.sidebarMenu);
      if (selected.has(itemId)) {
        if (selected.size <= 1) return f;
        selected.delete(itemId);
      } else {
        selected.add(itemId);
      }
      return {
        ...f,
        sidebarMenu: normalizeSidebarMenu(f.role, [...selected]),
      };
    });
  };

  const fetchCompanies = useCallback(() => {
    apiFetch('/api/companies/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') setCompanies(d.data || []);
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

  const resetPanel = () => {
    setPanelMode(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  };

  const handleNuovo = () => {
    setPanelMode('new');
    setSelectedUserId(null);
    setForm({
      ...EMPTY_FORM,
      companyId: companies[0]?.id ? String(companies[0].id) : '',
      sidebarMenu: getDefaultSidebarMenu('utente'),
    });
    setFormError(null);
  };

  const handleModifica = () => {
    if (!selectedUser) return;
    setPanelMode('edit');
    setForm({
      username: selectedUser.username,
      password: '',
      role: selectedUser.role,
      companyId: selectedUser.assigned_company?.id
        ? String(selectedUser.assigned_company.id)
        : (companies[0]?.id ? String(companies[0].id) : ''),
      sidebarMenu: selectedUser.sidebar_menu || getDefaultSidebarMenu(selectedUser.role),
    });
    setFormError(null);
  };

  const handleDelete = () => {
    if (!selectedUser) return;
    if (selectedUser.id === me?.id) {
      setError('Non puoi eliminare il tuo account.');
      return;
    }
    if (!window.confirm(`Eliminare l'utente "${selectedUser.username}"?`)) return;
    apiFetch(`/api/users/${selectedUser.id}/delete/`, { method: 'DELETE' })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setSelectedUserId(null);
          resetPanel();
          fetchUsers();
        } else {
          setError(d.error || 'Errore eliminazione');
        }
      })
      .catch(() => setError('Errore di rete'));
  };

  const handleSave = (e) => {
    e.preventDefault();
    if (!form.username.trim()) {
      setFormError('Username obbligatorio.');
      return;
    }
    if (panelMode === 'new' && !form.password.trim()) {
      setFormError('Password obbligatoria per il nuovo operatore.');
      return;
    }
    if (form.role === 'utente' && !form.companyId) {
      setFormError('Seleziona l\'azienda su cui può operare.');
      return;
    }
    if (!form.sidebarMenu.length) {
      setFormError('Seleziona almeno una voce del menu laterale.');
      return;
    }

    setSaving(true);
    setFormError(null);

    const payload = {
      username: form.username.trim(),
      password: form.password,
      role: form.role,
      sidebar_menu: form.sidebarMenu,
    };
    if (form.role === 'utente') payload.company_id = Number(form.companyId);

    const url = panelMode === 'new'
      ? '/api/users/create/'
      : `/api/users/${selectedUserId}/update/`;

    apiFetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          if (d.data?.id === me?.id) refreshUser();
          resetPanel();
          fetchUsers(false);
        } else {
          setFormError(d.error || 'Errore salvataggio');
        }
      })
      .catch(() => setFormError('Errore di rete'))
      .finally(() => setSaving(false));
  };

  const inp = {
    padding: '0.55rem 0.75rem',
    background: 'var(--bg-dark)',
    border: '1px solid var(--border)',
    color: 'white',
    borderRadius: '6px',
    fontSize: '0.9rem',
    width: '100%',
    boxSizing: 'border-box',
  };

  const btn = (active, disabled = false) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '0.35rem',
    padding: '0.55rem 1rem',
    background: active ? 'var(--accent)' : 'transparent',
    color: active ? 'white' : 'var(--text-main)',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '6px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    fontWeight: 600,
    fontSize: '0.88rem',
    opacity: disabled ? 0.5 : 1,
  });

  const card = {
    background: 'var(--bg-card)',
    border: '1px solid var(--border)',
    borderRadius: '12px',
    overflow: 'hidden',
  };

  const companyLabel = (u) => {
    if (u.role === 'amministratore') return 'Tutte le aziende';
    return u.assigned_company?.denominazione || '—';
  };

  return (
    <div style={{ maxWidth: '860px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '0.5rem' }}>Gestione Utenti</h1>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
        Seleziona un operatore dall&apos;elenco e modifica i dati, oppure creane uno nuovo.
      </p>

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.6rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', marginBottom: '1rem', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <button type="button" onClick={handleNuovo} style={btn(panelMode === 'new')}>
          <Plus size={16} /> Nuovo
        </button>
        <button
          type="button"
          onClick={handleModifica}
          disabled={!selectedUser || panelMode === 'new'}
          style={btn(panelMode === 'edit', !selectedUser || panelMode === 'new')}
        >
          <Pencil size={16} /> Modifica
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={!selectedUser || selectedUser?.id === me?.id}
          style={{
            ...btn(false, !selectedUser || selectedUser?.id === me?.id),
            color: 'var(--danger)',
            borderColor: 'var(--danger)',
          }}
        >
          <Trash2 size={16} /> Elimina
        </button>
      </div>

      {panelMode && (
        <div style={{ ...card, marginBottom: '1.25rem' }}>
          <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
            <h2 style={{ margin: 0, fontSize: '1rem' }}>
              {panelMode === 'new' ? 'Nuovo operatore' : `Modifica: ${selectedUser?.username || ''}`}
            </h2>
            <button type="button" onClick={resetPanel} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.85rem' }}>
              <X size={16} /> Chiudi
            </button>
          </div>

          <div style={{ padding: '1.25rem', display: 'grid', gridTemplateColumns: 'minmax(0, 1.4fr) minmax(220px, 0.9fr)', gap: '1.25rem' }}>
            <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '0.875rem' }}>
              {formError && (
                <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid var(--danger)', padding: '0.6rem 0.9rem', borderRadius: '6px', color: 'var(--danger)', fontSize: '0.85rem' }}>
                  {formError}
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Username *</label>
                  <input type="text" value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))} style={inp} placeholder="mario.rossi" />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>
                    {panelMode === 'new' ? 'Password *' : 'Nuova password'}
                  </label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    style={inp}
                    placeholder={panelMode === 'new' ? '••••••••' : 'Lascia vuoto per non cambiarla'}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Ruolo</label>
                  <select
                    value={form.role}
                    onChange={e => {
                      const role = e.target.value;
                      setForm(f => ({
                        ...f,
                        role,
                        sidebarMenu: normalizeSidebarMenu(role, f.sidebarMenu),
                      }));
                    }}
                    style={inp}
                  >
                    <option value="utente">Utente</option>
                    <option value="amministratore">Amministratore</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.35rem' }}>Azienda operativa</label>
                  {form.role === 'amministratore' ? (
                    <div style={{ ...inp, display: 'flex', alignItems: 'center', gap: '0.4rem', opacity: 0.9 }}>
                      <Building2 size={15} color="var(--accent)" />
                      Tutte le aziende
                    </div>
                  ) : (
                    <select
                      value={form.companyId}
                      onChange={e => setForm(f => ({ ...f, companyId: e.target.value }))}
                      style={inp}
                    >
                      <option value="">Seleziona azienda...</option>
                      {companies.map(c => (
                        <option key={c.id} value={c.id}>{c.denominazione || `Azienda #${c.id}`}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem' }}>
                <button type="submit" disabled={saving} style={{ ...btn(true), border: 'none' }}>
                  {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
                  Salva
                </button>
                <button type="button" onClick={resetPanel} style={btn(false)}>
                  Annulla
                </button>
              </div>
            </form>

            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '10px', padding: '0.9rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem', fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)' }}>
                <Menu size={15} color="var(--accent)" />
                Menu laterale visibile
              </div>
              <p style={{ margin: '0 0 0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                Tutte le voci del menu sono disponibili: seleziona quali mostrare a questo operatore.
              </p>
              <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {SIDEBAR_ITEMS.map(item => {
                  const Icon = item.icon;
                  const checked = form.sidebarMenu.includes(item.id);
                  return (
                    <li key={item.id}>
                      <label
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.45rem',
                          padding: '0.45rem 0.55rem',
                          borderRadius: '6px',
                          background: checked ? 'rgba(79,141,247,0.08)' : 'transparent',
                          border: `1px solid ${checked ? 'rgba(79,141,247,0.25)' : 'var(--border)'}`,
                          fontSize: '0.8rem',
                          color: 'var(--text-main)',
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleMenuItem(item.id)}
                          style={{ accentColor: 'var(--accent)' }}
                        />
                        <Icon size={15} color="var(--accent)" />
                        {item.label}
                      </label>
                    </li>
                  );
                })}
              </ul>
              <p style={{ margin: '0.75rem 0 0', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Anteprima attiva: {visibleNavItems.map(item => item.label).join(', ') || '—'}
              </p>
              {form.role === 'utente' && form.companyId && (
                <p style={{ margin: '0.75rem 0 0', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  Dati limitati a: <strong style={{ color: 'var(--text-main)' }}>{companies.find(c => String(c.id) === form.companyId)?.denominazione || '—'}</strong>
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <div style={card}>
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ margin: 0, fontSize: '1rem' }}>Operatori registrati</h2>
        </div>

        {loading ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento...</div>
        ) : users.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessun utente.</div>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, maxHeight: '360px', overflowY: 'auto' }}>
            {users.map((u, idx) => {
              const selected = u.id === selectedUserId;
              return (
                <li key={u.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedUserId(u.id);
                      if (panelMode === 'edit' && selectedUserId !== u.id) {
                        setPanelMode(null);
                      }
                    }}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '0.85rem 1.25rem',
                      border: 'none',
                      borderBottom: idx < users.length - 1 ? '1px solid var(--border)' : 'none',
                      background: selected ? 'rgba(79,141,247,0.12)' : 'transparent',
                      color: 'var(--text-main)',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.95rem', minWidth: '120px' }}>
                        {u.username}
                        {u.id === me?.id && <span style={{ marginLeft: '0.4rem', fontSize: '0.72rem', color: 'var(--text-muted)' }}>(tu)</span>}
                      </span>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                        padding: '0.15rem 0.55rem', borderRadius: '999px', fontSize: '0.72rem', fontWeight: 600,
                        background: u.role === 'amministratore' ? 'rgba(59,130,246,0.15)' : 'rgba(148,163,184,0.1)',
                        color: u.role === 'amministratore' ? 'var(--accent)' : 'var(--text-muted)',
                        border: `1px solid ${u.role === 'amministratore' ? 'var(--accent)' : 'var(--border)'}`,
                      }}>
                        {u.role === 'amministratore' ? <Shield size={11} /> : <User size={11} />}
                        {u.role === 'amministratore' ? 'Amministratore' : 'Utente'}
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        <Building2 size={12} /> {companyLabel(u)}
                      </span>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
