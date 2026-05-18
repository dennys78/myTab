import React, { useCallback, useEffect, useState } from 'react';
import { LayoutDashboard, Receipt, Settings, ChevronDown, ChevronRight, Euro, Cigarette, Edit2, Save, X, Calculator, Trash2, Menu, Tag, Sparkles, Users, LogOut, Loader2, Wallet, PiggyBank } from 'lucide-react';
import { apiFetch } from './api';
import { useAuth } from './auth';
import Login from './Login';
import AcquisisciChiusure from './AcquisisciChiusure';
import AcquisisciChiusureAI from './AcquisisciChiusureAI';
import RepartiManager from './RepartiManager';
import Impostazioni from './Impostazioni';
import GestioneUtenti from './GestioneUtenti';
import Versamenti from './Versamenti';
import FondoCassa from './FondoCassa';
import './index.css';

function AppShell() {
  const { user, logout } = useAuth();

  const [closures, setClosures] = useState([]);
  const [versamenti, setVersamenti] = useState([]);
  const [saldoCassa, setSaldoCassa] = useState(null);
  const [fondoCassa, setFondoCassa] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  const [editingId, setEditingId] = useState(null);
  const [editFormData, setEditFormData] = useState({});
  const [saving, setSaving] = useState(false);

  const isAdmin = user?.role === 'amministratore';

  // Gli utenti normali entrano direttamente nella pagina di acquisizione
  const [currentView, setCurrentView] = useState(isAdmin ? 'dashboard' : 'acquisisci-ai');

  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const fetchClosures = useCallback(() => {
    if (!isAdmin) return;
    apiFetch('/api/closures/list/')
      .then(res => res.json())
      .then(data => { if (data.status === 'success') setClosures(data.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isAdmin]);

  const fetchVersamenti = useCallback(() => {
    apiFetch('/api/versamenti/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setVersamenti(d.data);
          setSaldoCassa(d.saldo_cassa);
        }
      })
      .catch(() => {});
  }, []);

  const fetchFondoCassa = useCallback(() => {
    apiFetch('/api/fondo-cassa/')
      .then(r => r.json())
      .then(d => { if (d.status === 'success') setFondoCassa(d.totale); })
      .catch(() => {});
  }, []);

  const refreshDashboardData = useCallback(() => {
    fetchClosures();
    fetchVersamenti();
    fetchFondoCassa();
  }, [fetchClosures, fetchVersamenti, fetchFondoCassa]);

  useEffect(() => { refreshDashboardData(); }, [refreshDashboardData]);

  const totalIncassato = closures.reduce((acc, c) => acc + c.summary.totale, 0);
  const totaleVersato = versamenti.reduce((acc, v) => acc + v.importo_versato, 0);
  const totalContantiCalcolato = closures.reduce((acc, c) => acc + (c.summary.totale_cassetto || 0) + (c.summary.differenza || 0), 0) - totaleVersato;
  const totalContanti = saldoCassa ?? totalContantiCalcolato;

  const toggleRow = (id) => { if (editingId) return; setExpandedId(expandedId === id ? null : id); };

  const handleEditClick = (closure) => {
    setEditingId(closure.id);
    setEditFormData({ ...closure.summary, items: JSON.parse(JSON.stringify(closure.items)), deleted_item_ids: [] });
  };

  const handleCancelEdit = () => { setEditingId(null); setEditFormData({}); };

  const calcDifferenza = (s) => {
    const atteso = (s.totale || 0) - (s.pag_pos || 0) - (s.distrib || 0) - (s.reso_auto || 0) - (s.reso_cont || 0);
    return Math.round(((s.totale_cassetto || 0) - atteso) * 100) / 100;
  };

  const roundMoney = (value) => Math.round(value * 100) / 100;

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setEditFormData(prev => {
      const updated = { ...prev, [name]: parseFloat(value) || 0 };
      updated.differenza = calcDifferenza(updated);
      return updated;
    });
  };

  const handleItemInputChange = (itemId, field, value) => {
    setEditFormData(prev => ({
      ...prev,
      items: prev.items.map(item =>
        item.id === itemId ? { ...item, [field]: field === 'descrizione' ? value : (parseFloat(value) || 0) } : item
      )
    }));
  };

  const handleRemoveItem = (itemId) => {
    setEditFormData(prev => {
      const item = prev.items.find(i => i.id === itemId);
      if (!item) return prev;

      const amount = Number(item.entrate || item.saldo || 0);
      const updated = {
        ...prev,
        contanti: roundMoney(Math.max(0, (prev.contanti || 0) - amount)),
        totale: roundMoney(Math.max(0, (prev.totale || 0) - amount)),
        totale_cassetto: roundMoney(Math.max(0, (prev.totale_cassetto || 0) - amount)),
        items: prev.items.filter(i => i.id !== itemId),
        deleted_item_ids: [...(prev.deleted_item_ids || []), itemId],
      };
      updated.differenza = calcDifferenza(updated);
      return updated;
    });
  };

  const handleSaveEdit = (id) => {
    setSaving(true);
    apiFetch(`/api/closures/update/${id}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editFormData),
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') { refreshDashboardData(); setEditingId(null); }
        else alert('Errore durante il salvataggio: ' + data.error);
      })
      .catch(() => alert('Errore di rete durante il salvataggio.'))
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (!window.confirm("Sei sicuro di voler eliminare questa chiusura? L'operazione è irreversibile.")) return;
    apiFetch(`/api/closures/delete/${id}/`, { method: 'DELETE' })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') { refreshDashboardData(); if (expandedId === id) setExpandedId(null); }
        else alert("Errore durante l'eliminazione: " + data.error);
      })
      .catch(() => alert("Errore di rete durante l'eliminazione."));
  };

  const navigate = (view) => {
    setCurrentView(view);
    setIsMobileMenuOpen(false);
    if (view === 'dashboard') refreshDashboardData();
  };

  return (
    <div className="app-container">
      <div className={`sidebar-overlay ${isMobileMenuOpen ? 'show' : ''}`} onClick={() => setIsMobileMenuOpen(false)} />

      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cigarette size={24} color="var(--accent)" />
          myTab
        </div>

        <nav className="nav-links">
          {isAdmin && (
            <>
              <div className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`} onClick={() => navigate('dashboard')}>
                <LayoutDashboard size={20} /><span>Dashboard</span>
              </div>
              <div className="nav-item">
                <Receipt size={20} /><span>Chiusure Cassa</span>
              </div>
            </>
          )}

          <div className={`nav-item ${currentView === 'acquisisci-ai' ? 'active' : ''}`} onClick={() => navigate('acquisisci-ai')}>
            <Sparkles size={20} /><span>Acquisisci con IA</span>
          </div>

          <div className={`nav-item ${currentView === 'versamenti' ? 'active' : ''}`} onClick={() => navigate('versamenti')}>
            <Wallet size={20} /><span>Versamenti</span>
          </div>

          <div className={`nav-item ${currentView === 'fondo-cassa' ? 'active' : ''}`} onClick={() => navigate('fondo-cassa')}>
            <PiggyBank size={20} /><span>Fondo Cassa</span>
          </div>

          {isAdmin && (
            <>
              <div className={`nav-item ${currentView === 'reparti' ? 'active' : ''}`} onClick={() => navigate('reparti')}>
                <Tag size={20} /><span>Reparti</span>
              </div>
              <div className={`nav-item ${currentView === 'utenti' ? 'active' : ''}`} onClick={() => navigate('utenti')}>
                <Users size={20} /><span>Utenti</span>
              </div>
              <div className={`nav-item ${currentView === 'impostazioni' ? 'active' : ''}`} onClick={() => navigate('impostazioni')} style={{ marginTop: 'auto' }}>
                <Settings size={20} /><span>Impostazioni</span>
              </div>
            </>
          )}
        </nav>

        {/* Footer sidebar: utente loggato + logout */}
        <div style={{ padding: '1rem', borderTop: '1px solid var(--border)', marginTop: isAdmin ? '0' : 'auto' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Connesso come <strong style={{ color: 'var(--text-main)' }}>{user?.username}</strong>
          </div>
          <button onClick={logout} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', width: '100%', padding: '0.5rem 0.6rem', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)', borderRadius: '6px', cursor: 'pointer', fontSize: '0.85rem' }}>
            <LogOut size={15} /> Esci
          </button>
        </div>
      </aside>

      <main className="main-content">
        <div className="mobile-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 'bold', fontSize: '1.25rem', color: 'var(--accent)' }}>
            <Cigarette size={24} />myTab
          </div>
          <button className="menu-button" onClick={() => setIsMobileMenuOpen(true)}>
            <Menu size={24} />
          </button>
        </div>

        {currentView === 'acquisisci' ? (
          <AcquisisciChiusure onBack={() => { navigate('dashboard'); refreshDashboardData(); }} />
        ) : currentView === 'acquisisci-ai' ? (
          <AcquisisciChiusureAI onBack={() => { navigate(isAdmin ? 'dashboard' : 'acquisisci-ai'); refreshDashboardData(); }} />
        ) : currentView === 'reparti' ? (
          <RepartiManager />
        ) : currentView === 'impostazioni' ? (
          <Impostazioni />
        ) : currentView === 'utenti' ? (
          <GestioneUtenti />
        ) : currentView === 'versamenti' ? (
          <Versamenti />
        ) : currentView === 'fondo-cassa' ? (
          <FondoCassa />
        ) : (
          <>
            <h1>Panoramica Chiusure</h1>

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-title">Totale Generale (Mese)</div>
                <div className="stat-value">€ {totalIncassato.toFixed(2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Contanti in Cassa</div>
                <div className={`stat-value ${totalContanti >= 0 ? 'success' : 'danger'}`}>€ {totalContanti.toFixed(2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Fondo Cassa</div>
                <div className="stat-value" style={{ color: '#f59e0b' }}>€ {fondoCassa.toFixed(2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Chiusure Ricevute</div>
                <div className="stat-value">{closures.length}</div>
              </div>
            </div>

            <div className="table-container">
              {loading ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Caricamento dati in corso...</div>
              ) : closures.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Nessuna chiusura presente.</div>
              ) : (
                <div className="table-responsive-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th></th>
                        <th>Data</th>
                        <th>Operatore</th>
                        <th>Contanti</th>
                        <th>Pag. POS</th>
                        <th>Totale Generale</th>
                        <th>Azioni</th>
                      </tr>
                    </thead>
                    <tbody>
                      {closures.map(closure => (
                        <React.Fragment key={closure.id}>
                          <tr onClick={() => toggleRow(closure.id)} className={expandedId === closure.id ? 'expanded-row' : ''}>
                            <td style={{ width: '40px' }}>
                              {expandedId === closure.id ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                            </td>
                            <td>{closure.date}</td>
                            <td>{closure.operator}</td>
                            <td>€ {closure.summary.contanti.toFixed(2)}</td>
                            <td>€ {closure.summary.pag_pos.toFixed(2)}</td>
                            <td style={{ fontWeight: 'bold', color: 'var(--accent)' }}>€ {closure.summary.totale.toFixed(2)}</td>
                            <td>
                              <button onClick={(e) => { e.stopPropagation(); handleDelete(closure.id); }} title="Elimina"
                                style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
                                <Trash2 size={16} color="var(--danger)" />
                              </button>
                            </td>
                          </tr>

                          {expandedId === closure.id && (
                            <tr>
                              <td colSpan="7" style={{ padding: 0, borderBottom: 'none' }}>
                                <div className="expanded-content">
                                  <div className="summary-section" style={{ marginBottom: '2rem', padding: '1.25rem', background: 'var(--bg-card)', borderRadius: '14px', border: '1px solid var(--border)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                      <h2 style={{ fontSize: '1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Calculator size={16} color="var(--accent)" /> Riepilogo Totali
                                      </h2>
                                      {editingId === closure.id ? (
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                          <button onClick={() => handleSaveEdit(closure.id)} disabled={saving}
                                            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--success)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Save size={14} /> {saving ? 'Salvataggio...' : 'Salva'}
                                          </button>
                                          <button onClick={handleCancelEdit} disabled={saving}
                                            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer' }}>
                                            <X size={14} /> Annulla
                                          </button>
                                        </div>
                                      ) : (
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                          <button onClick={(e) => { e.stopPropagation(); handleEditClick(closure); }}
                                            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Edit2 size={14} /> Modifica
                                          </button>
                                          <button onClick={(e) => { e.stopPropagation(); handleDelete(closure.id); }}
                                            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--danger)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Trash2 size={14} /> Elimina
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
                                      {Object.entries(closure.summary).map(([key, value]) => {
                                        const label = key.replace(/_/g, ' ');
                                        const editVal = editingId === closure.id ? (editFormData[key] ?? value) : value;
                                        const isDiff = key === 'differenza';
                                        return (
                                          <div key={key}>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize', marginBottom: '0.25rem' }}>
                                              {label}
                                            </div>
                                            {isDiff ? (
                                              <div style={{ fontWeight: '700', color: editVal > 0 ? 'var(--success)' : editVal < 0 ? 'var(--danger)' : 'var(--text-muted)' }}>
                                                {editVal >= 0 ? '+' : ''}€ {Number(editVal).toFixed(2)}
                                              </div>
                                            ) : editingId === closure.id ? (
                                              <input type="number" name={key} value={editFormData[key] === 0 ? '' : editFormData[key]} onChange={handleInputChange}
                                                style={{ width: '100%', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }}
                                                placeholder={value} />
                                            ) : (
                                              <div style={{ fontWeight: '600' }}>€ {value.toFixed(2)}</div>
                                            )}
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>

                                  <h2 style={{ fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Euro size={16} color="var(--accent)" /> Dettaglio Reparti
                                  </h2>
                                  <table className="inner-table">
                                    <thead>
                                      <tr>
                                        <th>Descrizione</th><th>Entrate</th><th>Uscite</th><th>Saldo</th>{editingId === closure.id && <th>Azioni</th>}
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {closure.items.length > 0 ? closure.items.map(item => {
                                        const editItem = editingId === closure.id ? editFormData.items.find(i => i.id === item.id) : item;
                                        return (
                                          <tr key={item.id} style={{ cursor: 'default' }}>
                                            <td>{editingId === closure.id ? <input type="text" value={editItem?.descrizione || ''} onChange={(e) => handleItemInputChange(item.id, 'descrizione', e.target.value)} style={{ width: '100%', minWidth: '120px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} /> : item.descrizione}</td>
                                            <td>{editingId === closure.id ? <input type="number" value={editItem?.entrate === 0 ? '' : editItem?.entrate} onChange={(e) => handleItemInputChange(item.id, 'entrate', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} /> : <span style={{ color: item.entrate > 0 ? 'var(--success)' : 'inherit' }}>€ {item.entrate.toFixed(2)}</span>}</td>
                                            <td>{editingId === closure.id ? <input type="number" value={editItem?.uscite === 0 ? '' : editItem?.uscite} onChange={(e) => handleItemInputChange(item.id, 'uscite', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} /> : <span style={{ color: item.uscite > 0 ? 'var(--danger)' : 'inherit' }}>€ {item.uscite.toFixed(2)}</span>}</td>
                                            <td>{editingId === closure.id ? <input type="number" value={editItem?.saldo === 0 ? '' : editItem?.saldo} onChange={(e) => handleItemInputChange(item.id, 'saldo', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} /> : <span>€ {item.saldo.toFixed(2)}</span>}</td>
                                            {editingId === closure.id && (
                                              <td>
                                                <button
                                                  onClick={() => handleRemoveItem(item.id)}
                                                  title="Elimina incasso"
                                                  style={{ background: 'transparent', border: 'none', color: 'var(--danger)', cursor: 'pointer', padding: '0.25rem' }}
                                                >
                                                  <Trash2 size={15} />
                                                </button>
                                              </td>
                                            )}
                                          </tr>
                                        );
                                      }) : (
                                        <tr><td colSpan={editingId === closure.id ? 5 : 4} style={{ textAlign: 'center' }}>Nessuna voce trovata</td></tr>
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

export default function App() {
  const { user } = useAuth();

  if (user === undefined) {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--bg-dark)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Loader2 size={36} className="spin" color="var(--accent)" />
      </div>
    );
  }

  if (user === null) return <Login />;

  return <AppShell />;
}

