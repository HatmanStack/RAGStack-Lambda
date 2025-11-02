import React, { useEffect } from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { Box, Container, Header, SpaceBetween } from '@cloudscape-design/components';

// Component to handle redirect after authentication
// Extracted to comply with Rules of Hooks (hooks must be at top level)
const RedirectOnAuth = ({ user, from, navigate }) => {
  useEffect(() => {
    if (user) {
      navigate(from, { replace: true });
    }
  }, [user, from, navigate]);

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
