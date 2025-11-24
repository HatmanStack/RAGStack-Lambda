import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider';
import { Box, Spinner } from '@cloudscape-design/components';

export const RequireAuth = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  console.log('[RequireAuth] Render - loading:', loading, 'isAuthenticated:', isAuthenticated, 'path:', location.pathname);

  if (loading) {
    console.log('[RequireAuth] Showing loading spinner');
    return (
      <Box textAlign="center" padding="xxl">
        <Spinner size="large" />
      </Box>
    );
  }

  if (!isAuthenticated) {
    console.log('[RequireAuth] Not authenticated, redirecting to /login');
    // Redirect to login page but save the location they were trying to access
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  console.log('[RequireAuth] Authenticated, rendering children');
  return children;
};
