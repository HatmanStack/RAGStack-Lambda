import React, { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { fetchAuthSession, getCurrentUser, signOut } from 'aws-amplify/auth';

const AuthContext = createContext(null);

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const checkUser = useCallback(async () => {
    console.log('[AuthProvider] checkUser() called');
    try {
      const currentUser = await getCurrentUser();
      const session = await fetchAuthSession();

      console.log('[AuthProvider] User authenticated:', currentUser.username);
      setUser({
        username: currentUser.username,
        userId: currentUser.userId,
        signInDetails: currentUser.signInDetails,
        tokens: session.tokens
      });
    } catch (err) {
      // User not signed in
      console.log('[AuthProvider] No authenticated user:', err.name);
      setUser(null);
    } finally {
      setLoading(false);
      console.log('[AuthProvider] checkUser() complete, loading set to false');
    }
  }, []);

  useEffect(() => {
    console.log('[AuthProvider] Initial mount - calling checkUser()');
    checkUser();
  }, [checkUser]);

  const logout = useCallback(async () => {
    try {
      await signOut();
      setUser(null);
    } catch (err) {
      console.error('Error signing out:', err);
      setError(err.message);
    }
  }, []);

  const value = useMemo(() => ({
    user,
    loading,
    error,
    isAuthenticated: !!user,
    checkUser,
    logout
  }), [user, loading, error, checkUser, logout]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
