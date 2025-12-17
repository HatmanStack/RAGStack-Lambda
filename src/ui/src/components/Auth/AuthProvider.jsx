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
    try {
      const currentUser = await getCurrentUser();
      const session = await fetchAuthSession();

      setUser({
        username: currentUser.username,
        userId: currentUser.userId,
        signInDetails: currentUser.signInDetails,
        tokens: session.tokens
      });
    } catch (err) {
      // Distinguish between expected "not authenticated" vs actual errors
      const errorName = err?.name || 'Unknown';
      const isAuthError = errorName.includes('NotAuthorizedException') ||
                         errorName.includes('UserUnAuthenticatedException') ||
                         errorName === 'UserNotFoundException';

      // Only log unexpected errors (network, config issues)
      if (!isAuthError) {
        console.error('[AuthProvider] Error checking auth status:', errorName, err.message || err);
      }

      // Always set user to null on any error (same UI behavior)
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
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
