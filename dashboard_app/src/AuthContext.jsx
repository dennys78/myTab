import { useState, useEffect } from 'react';
import { apiFetch } from './api';
import { AuthContext } from './auth';

export function AuthProvider({ children }) {
  // undefined = caricamento in corso, null = non autenticato, object = utente
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    apiFetch('/api/auth/me/')
      .then(r => r.json())
      .then(d => setUser(d.status === 'success' ? d.data : null))
      .catch(() => setUser(null));
  }, []);

  const login = (userData) => setUser(userData);

  const logout = () => {
    apiFetch('/api/auth/logout/', { method: 'POST' }).catch(() => {});
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
