import React, { useEffect, useState } from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { Box, Container, Header, SpaceBetween, Spinner } from '@cloudscape-design/components';
import { useAuth } from './AuthProvider';

// Component to handle redirect after authentication
// Extracted to comply with Rules of Hooks (hooks must be at top level)
const RedirectOnAuth = ({ user, from, navigate }) => {
  const { checkUser } = useAuth();
  const [syncing, setSyncing] = useState(false);
  const [syncError, setSyncError] = useState(null);

  useEffect(() => {
    if (user && !syncing && !syncError) {
      setSyncing(true);
      // Update AuthProvider state before navigating
      checkUser().then(() => {
        navigate(from, { replace: true });
      }).catch((err) => {
        console.error('[Login] Failed to sync AuthProvider:', err);
        setSyncError(err);  // Prevent infinite retry loop
        setSyncing(false);
      });
    }
  }, [user, from, navigate, checkUser, syncing, syncError]);

  if (syncError) {
    return (
      <Box textAlign="center" padding="l">
        <SpaceBetween size="s">
          <Box variant="p" color="text-status-error">
            Failed to complete sign in. Please try refreshing the page.
          </Box>
        </SpaceBetween>
      </Box>
    );
  }

  if (syncing) {
    return (
      <Box textAlign="center" padding="l">
        <SpaceBetween size="s">
          <Spinner size="large" />
          <Box variant="p" color="text-body-secondary">
            Signing you in...
          </Box>
        </SpaceBetween>
      </Box>
    );
  }

  return null;
};

export const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();

  // Get the page they were trying to access, or default to dashboard
  const from = location.state?.from?.pathname || '/';

  return (
    <Box textAlign="center" padding={{ top: 'xxl' }}>
      <Container>
        <SpaceBetween size="l">
          <Header variant="h1">RAGStack-Lambda</Header>
          <Header variant="h3">
            Serverless Document Processing & Knowledge Base Search
          </Header>

          <Authenticator
            loginMechanisms={['email']}
            signUpAttributes={['email']}
          >
            {({ signOut: _signOut, user }) => ( // eslint-disable-line no-unused-vars
              <RedirectOnAuth user={user} from={from} navigate={navigate} />
            )}
          </Authenticator>
        </SpaceBetween>
      </Container>
    </Box>
  );
};
