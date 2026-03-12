import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider } from './components/Auth/AuthProvider';
import { RequireAuth } from './components/Auth/RequireAuth';
import { Login } from './components/Auth/Login';
import { AppLayout } from './components/Layout/AppLayout';
import { Dashboard } from './components/Dashboard';
import { Upload } from './components/Upload';
import { Search } from './components/Search';
import { Chat } from './components/Chat';
import { Settings } from './components/Settings';
import { Scrape } from './components/Scrape';
import { ErrorBoundary } from './components/common/ErrorBoundary';

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route
            path="/*"
            element={
              <RequireAuth>
                <AppLayout>
                  <Routes>
                    <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
                    <Route path="/upload" element={<ErrorBoundary><Upload /></ErrorBoundary>} />
                    <Route path="/scrape" element={<ErrorBoundary><Scrape /></ErrorBoundary>} />
                    <Route path="/search" element={<ErrorBoundary><Search /></ErrorBoundary>} />
                    <Route path="/chat" element={<ErrorBoundary><Chat /></ErrorBoundary>} />
                    <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
                  </Routes>
                </AppLayout>
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
