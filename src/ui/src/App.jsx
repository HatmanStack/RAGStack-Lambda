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
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/upload" element={<Upload />} />
                    <Route path="/scrape" element={<Scrape />} />
                    <Route path="/search" element={<Search />} />
                    <Route path="/chat" element={<Chat />} />
                    <Route path="/settings" element={<Settings />} />
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
