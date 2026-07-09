import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';

import { AuthPage } from '../pages/AuthPage/AuthPage';
import { ChatPage } from '../pages/ChatPage/ChatPage';
import { JoinInvitePage } from '../pages/JoinInvitePage/JoinInvitePage';
import { SettingsPage } from '../pages/SettingsPage/SettingsPage';
import { refreshSession } from '../features/auth/api';
import { useSessionStore } from '../entities/user/store';
import { setTokenRefresher } from '../shared/api/client';
import { AppLayout } from './AppLayout';
import { AppProviders } from './providers';
import { RequireAuth } from './RequireAuth';

function Bootstrap() {
  const setSession = useSessionStore((s) => s.setSession);
  const setStatus = useSessionStore((s) => s.setStatus);

  // Авто-обновление access-токена при 401 в любом запросе (см. shared/api/client).
  useEffect(() => {
    setTokenRefresher(async () => {
      try {
        const { user, token } = await refreshSession();
        setSession(user, token);
        return token;
      } catch {
        setStatus('anonymous');
        return null;
      }
    });
    return () => setTokenRefresher(null);
  }, [setSession, setStatus]);

  useEffect(() => {
    let cancelled = false;
    setStatus('loading');
    refreshSession()
      .then(({ user, token }) => {
        if (!cancelled) setSession(user, token);
      })
      .catch(() => {
        if (!cancelled) setStatus('anonymous');
      });
    return () => {
      cancelled = true;
    };
  }, [setSession, setStatus]);

  return null;
}

export function App() {
  return (
    <AppProviders>
      <BrowserRouter>
        <Bootstrap />
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/join/:token" element={<JoinInvitePage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<ChatPage />} />
            <Route path="chat/:chatId" element={<ChatPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AppProviders>
  );
}
