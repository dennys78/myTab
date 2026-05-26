import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from './api';
import { AuthContext } from './auth';

export function AuthProvider({ children }) {
  // undefined = caricamento in corso, null = non autenticato, object = utente
  const [user, setUser] = useState(undefined);

  const refreshUser = useCallback(() => (
    apiFetch('/api/auth/me/')
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          setUser(d.data);
          return d.data;
        }
        setUser(null);
        return null;
      })
      .catch(() => {
        setUser(null);
        return null;
      })
  ), []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = (userData) => setUser(userData);

  const logout = () => {
    apiFetch('/api/auth/logout/', { method: 'POST' }).catch(() => {});
    setUser(null);
  };

  const switchCompany = useCallback((companyId) => (
    apiFetch('/api/companies/switch/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ company_id: Number(companyId) }),
    })
      .then(r => r.json())
      .then(d => {
        if (d.status === 'success') {
          window.location.reload();
        }
        return d;
      })
  ), []);

  return (
    <AuthContext.Provider value={{ user, login, logout, refreshUser, switchCompany }}>
      {children}
    </AuthContext.Provider>
  );
}
