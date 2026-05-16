import React, { useState, useEffect } from 'react';
import { LayoutDashboard, Receipt, Settings, ChevronDown, ChevronRight, Euro, Cigarette, Edit2, Save, X, Calculator, Trash2, Menu, Camera } from 'lucide-react';
import AcquisisciChiusure from './AcquisisciChiusure';
import './index.css';

export default function App() {
  const [closures, setClosures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  // Edit state
  const [editingId, setEditingId] = useState(null);
  const [editFormData, setEditFormData] = useState({});
  const [saving, setSaving] = useState(false);

  // Navigation state
  const [currentView, setCurrentView] = useState('dashboard');

  // Mobile Menu state
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const fetchClosures = () => {
    fetch('/api/closures/list/')
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          setClosures(data.data);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching closures:", err);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchClosures();
  }, []);

  const totalIncassato = closures.reduce((acc, c) => acc + c.summary.totale, 0);
  const totalContanti = closures.reduce((acc, c) => acc + c.summary.contanti, 0);

  const toggleRow = (id) => {
    if (editingId) return;
    setExpandedId(expandedId === id ? null : id);
  };

  const handleEditClick = (closure) => {
    setEditingId(closure.id);
    setEditFormData({
      ...closure.summary,
      items: JSON.parse(JSON.stringify(closure.items))
    });
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditFormData({});
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setEditFormData(prev => ({
      ...prev,
      [name]: parseFloat(value) || 0
    }));
  };

  const handleItemInputChange = (itemId, field, value) => {
    setEditFormData(prev => ({
      ...prev,
      items: prev.items.map(item =>
        item.id === itemId ? { ...item, [field]: field === 'descrizione' ? value : (parseFloat(value) || 0) } : item
      )
    }));
  };

  const handleSaveEdit = (id) => {
    setSaving(true);
    fetch(`/api/closures/update/${id}/`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editFormData),
    })
      .then(res => res.json())
      .then(data => {
        if (data.status === 'success') {
          fetchClosures();
          setEditingId(null);
        } else {
          alert("Errore durante il salvataggio: " + data.error);
        }
      })
      .catch(err => {
        console.error("Errore salvataggio:", err);
        alert("Errore di rete durante il salvataggio.");
      })
      .finally(() => setSaving(false));
  };

  const handleDelete = (id) => {
    if (window.confirm("Sei sicuro di voler eliminare questa chiusura? L'operazione è irreversibile.")) {
      fetch(`/api/closures/delete/${id}/`, { method: 'DELETE' })
        .then(res => res.json())
        .then(data => {
          if (data.status === 'success') {
            fetchClosures();
            if (expandedId === id) setExpandedId(null);
          } else {
            alert("Errore durante l'eliminazione: " + data.error);
          }
        })
        .catch(err => {
          console.error("Errore eliminazione:", err);
          alert("Errore di rete durante l'eliminazione.");
        });
    }
  };

  return (
    <div className="app-container">
      {/* Mobile Sidebar Overlay */}
      <div
        className={`sidebar-overlay ${isMobileMenuOpen ? 'show' : ''}`}
        onClick={() => setIsMobileMenuOpen(false)}
      ></div>

      {/* Sidebar */}
      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Cigarette size={24} color="var(--accent)" />
          myTab
        </div>
        <nav className="nav-links">
          <div
            className={`nav-item ${currentView === 'dashboard' ? 'active' : ''}`}
            onClick={() => { setCurrentView('dashboard'); setIsMobileMenuOpen(false); }}
          >
            <LayoutDashboard size={20} />
            <span>Dashboard</span>
          </div>
          <div className="nav-item">
            <Receipt size={20} />
            <span>Chiusure Cassa</span>
          </div>

          <div style={{ marginTop: '1rem', marginBottom: '0.5rem', paddingLeft: '1rem', fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 'bold' }}>
            Utility
          </div>
          <div
            className={`nav-item ${currentView === 'acquisisci' ? 'active' : ''}`}
            onClick={() => { setCurrentView('acquisisci'); setIsMobileMenuOpen(false); }}
          >
            <Camera size={20} />
            <span>Acquisisci Chiusure</span>
          </div>

          <div className="nav-item" style={{ marginTop: 'auto' }}>
            <Settings size={20} />
            <span>Impostazioni</span>
          </div>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Mobile Header */}
        <div className="mobile-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 'bold', fontSize: '1.25rem', color: 'var(--accent)' }}>
            <Cigarette size={24} />
            myTab
          </div>
          <button className="menu-button" onClick={() => setIsMobileMenuOpen(true)}>
            <Menu size={24} />
          </button>
        </div>

        {currentView === 'acquisisci' ? (
          <AcquisisciChiusure onBack={() => { setCurrentView('dashboard'); fetchClosures(); }} />
        ) : (
          <>
            <h1>Panoramica Chiusure</h1>

            {/* Stats */}
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-title">Totale Generale (Mese)</div>
                <div className="stat-value">€ {totalIncassato.toFixed(2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Contanti in Cassa</div>
                <div className="stat-value success">€ {totalContanti.toFixed(2)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-title">Chiusure Ricevute</div>
                <div className="stat-value">{closures.length}</div>
              </div>
            </div>

            {/* Table */}
            <div className="table-container">
              {loading ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Caricamento dati in corso...
                </div>
              ) : closures.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                  Nessuna chiusura presente.
                </div>
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
                            <td style={{ fontWeight: 'bold', color: 'var(--accent)' }}>
                              € {closure.summary.totale.toFixed(2)}
                            </td>
                            <td>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDelete(closure.id); }}
                                title="Elimina"
                                style={{ background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center' }}
                              >
                                <Trash2 size={16} color="var(--danger)" />
                              </button>
                            </td>
                          </tr>

                          {expandedId === closure.id && (
                            <tr>
                              <td colSpan="7" style={{ padding: 0, borderBottom: 'none' }}>
                                <div className="expanded-content">
                                  {/* Summary Edit Section */}
                                  <div className="summary-section" style={{ marginBottom: '2rem', padding: '1rem', background: 'var(--bg-dark)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                      <h2 style={{ fontSize: '1rem', margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                        <Calculator size={16} color="var(--accent)" />
                                        Riepilogo Totali
                                      </h2>
                                      {editingId === closure.id ? (
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                          <button onClick={() => handleSaveEdit(closure.id)} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--success)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Save size={14} /> {saving ? 'Salvataggio...' : 'Salva'}
                                          </button>
                                          <button onClick={handleCancelEdit} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: '4px', cursor: 'pointer' }}>
                                            <X size={14} /> Annulla
                                          </button>
                                        </div>
                                      ) : (
                                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                                          <button onClick={(e) => { e.stopPropagation(); handleEditClick(closure); }} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Edit2 size={14} /> Modifica
                                          </button>
                                          <button onClick={(e) => { e.stopPropagation(); handleDelete(closure.id); }} style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem 0.75rem', background: 'var(--danger)', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
                                            <Trash2 size={14} /> Elimina
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem' }}>
                                      {Object.entries(closure.summary).map(([key, value]) => (
                                        <div key={key}>
                                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize', marginBottom: '0.25rem' }}>
                                            {key.replace('_', ' ')}
                                          </div>
                                          {editingId === closure.id ? (
                                            <input
                                              type="number"
                                              name={key}
                                              value={editFormData[key] === 0 ? '' : editFormData[key]}
                                              onChange={handleInputChange}
                                              style={{ width: '100%', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }}
                                              placeholder={value}
                                            />
                                          ) : (
                                            <div style={{ fontWeight: '600' }}>€ {value.toFixed(2)}</div>
                                          )}
                                        </div>
                                      ))}
                                    </div>
                                  </div>

                                  <h2 style={{ fontSize: '1rem', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                    <Euro size={16} color="var(--accent)" />
                                    Dettaglio Reparti
                                  </h2>
                                  <table className="inner-table">
                                    <thead>
                                      <tr>
                                        <th>Descrizione</th>
                                        <th>Entrate</th>
                                        <th>Uscite</th>
                                        <th>Saldo</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {closure.items.length > 0 ? closure.items.map(item => {
                                        const editItem = editingId === closure.id ? editFormData.items.find(i => i.id === item.id) : item;
                                        return (
                                          <tr key={item.id} style={{ cursor: 'default' }}>
                                            <td>
                                              {editingId === closure.id ? (
                                                <input type="text" value={editItem?.descrizione || ''} onChange={(e) => handleItemInputChange(item.id, 'descrizione', e.target.value)} style={{ width: '100%', minWidth: '120px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} />
                                              ) : item.descrizione}
                                            </td>
                                            <td>
                                              {editingId === closure.id ? (
                                                <input type="number" value={editItem?.entrate === 0 ? '' : editItem?.entrate} onChange={(e) => handleItemInputChange(item.id, 'entrate', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} />
                                              ) : <span style={{ color: item.entrate > 0 ? 'var(--success)' : 'inherit' }}>€ {item.entrate.toFixed(2)}</span>}
                                            </td>
                                            <td>
                                              {editingId === closure.id ? (
                                                <input type="number" value={editItem?.uscite === 0 ? '' : editItem?.uscite} onChange={(e) => handleItemInputChange(item.id, 'uscite', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} />
                                              ) : <span style={{ color: item.uscite > 0 ? 'var(--danger)' : 'inherit' }}>€ {item.uscite.toFixed(2)}</span>}
                                            </td>
                                            <td>
                                              {editingId === closure.id ? (
                                                <input type="number" value={editItem?.saldo === 0 ? '' : editItem?.saldo} onChange={(e) => handleItemInputChange(item.id, 'saldo', e.target.value)} style={{ width: '80px', padding: '0.25rem 0.5rem', background: 'var(--bg-card)', border: '1px solid var(--accent)', color: 'var(--text-main)', borderRadius: '4px' }} />
                                              ) : <span>€ {item.saldo.toFixed(2)}</span>}
                                            </td>
                                          </tr>
                                        );
                                      }) : (
                                        <tr><td colSpan="4" style={{ textAlign: 'center' }}>Nessuna voce trovata</td></tr>
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
