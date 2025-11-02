import React, { useEffect } from 'react';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { useNavigate, useLocation } from 'react-router-dom';
import { Box, Container, Header, SpaceBetween } from '@cloudscape-design/components';

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
            {({ signOut: _signOut, user }) => { // eslint-disable-line no-unused-vars
              // Once authenticated, navigate to the intended destination
              // Use useEffect to avoid updating BrowserRouter during render
              useEffect(() => {
                if (user) {
                  navigate(from, { replace: true });
                }
              }, [user, navigate, from]);

              return null;
            }}
          </Authenticator>
        </SpaceBetween>
      </Container>
    </Box>
  );
};
