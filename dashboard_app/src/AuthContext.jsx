import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // undefined = caricamento in corso, null = non autenticato, object = utente
  const [user, setUser] = useState(undefined);

  useEffect(() => {
    fetch('/api/auth/me/')
      .then(r => r.json())
      .then(d => setUser(d.status === 'success' ? d.data : null))
      .catch(() => setUser(null));
  }, []);

  const login = (userData) => setUser(userData);

  const logout = () => {
    fetch('/api/auth/logout/', { method: 'POST' }).catch(() => {});
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
